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
   */
  async getSession(sessionId: number): Promise<SessionResponse> {
    return this.request<SessionResponse>(`/session/${sessionId}`);
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
