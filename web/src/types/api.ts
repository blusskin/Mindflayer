// API Types for Orange Nethack

export type SessionStatus = 'pending' | 'active' | 'playing' | 'ended';

// Request types
export interface PlayRequest {
  lightning_address?: string;
  email?: string;
}

export interface SetAddressRequest {
  lightning_address: string;
}

// Response types
export interface InvoiceResponse {
  session_id: number;
  access_token: string;
  payment_request: string;
  payment_hash: string;
  amount_sats: number;
  expires_at: string | null;
}

export interface SessionResponse {
  id: number;
  status: SessionStatus;
  username?: string;
  password?: string;
  ssh_command?: string;
  lightning_address?: string;
  ante_sats: number;
  created_at: string;
}

export interface PotResponse {
  balance_sats: number;
  ante_sats: number;
}

export interface GameResult {
  id: number;
  username: string;
  death_reason: string | null;
  score: number;
  turns: number;
  ascended: boolean;
  payout_sats: number | null;
  ended_at: string;
}

export interface StatsResponse {
  pot_balance: number;
  total_games: number;
  total_ascensions: number;
  high_score: number | null;
  avg_score: number | null;
  recent_games: GameResult[];
  leaderboard: GameResult[];
  ascensions: GameResult[];
}

export interface HealthResponse {
  status: string;
  pot_balance: number;
  active_sessions: number;
  mock_mode: boolean;
}

// API Error
export interface ApiError {
  detail: string;
}
