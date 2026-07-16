export interface AuthSession {
  authenticated: boolean;
  username: string | null;
}

export interface LoginRequest {
  username: string;
  password: string;
}
