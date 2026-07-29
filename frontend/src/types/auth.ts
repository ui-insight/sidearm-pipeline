export interface AuthSession {
  authenticated: boolean;
  username: string | null;
  roles: string[];
}

export interface LoginRequest {
  username: string;
  password: string;
}
