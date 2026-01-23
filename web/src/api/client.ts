// API Client for Orange Nethack
import type {
  PlayRequest,
  InvoiceResponse,
  SessionResponse,
  PotResponse,
  StatsResponse,
  SetAddressRequest,
  ApiError,
} from '@/types/api';

const API_BASE = '/api';

class ApiClient {
  private async request<T>(
    endpoint: string,
    options?: RequestInit
  ): Promise<T> {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });

    if (!response.ok) {
      const error: ApiError = await response.json().catch(() => ({
        detail: `HTTP ${response.status}: ${response.statusText}`,
      }));
      throw new Error(error.detail);
    }

    return response.json();
  }

  /**
   * Create a new play session and get a Lightning invoice
   */
  async createSession(data?: PlayRequest): Promise<InvoiceResponse> {
    return this.request<InvoiceResponse>('/play', {
      method: 'POST',
      body: JSON.stringify(data ?? {}),
    });
  }

  /**
   * Get session status and credentials (if paid)
   * Token is required for active/playing sessions to access credentials
   */
  async getSession(sessionId: number, token?: string): Promise<SessionResponse> {
    const url = token
      ? `/session/${sessionId}?token=${encodeURIComponent(token)}`
      : `/session/${sessionId}`;
    return this.request<SessionResponse>(url);
  }

  /**
   * Set payout address for a session
   */
  async setAddress(
    sessionId: number,
    data: SetAddressRequest
  ): Promise<{ status: string; lightning_address: string }> {
    return this.request(`/play/${sessionId}/address`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  /**
   * Get current pot balance and ante
   */
  async getPot(): Promise<PotResponse> {
    return this.request<PotResponse>('/pot');
  }

  /**
   * Get stats, leaderboard, and recent games
   */
  async getStats(): Promise<StatsResponse> {
    return this.request<StatsResponse>('/stats');
  }
}

export const api = new ApiClient();
