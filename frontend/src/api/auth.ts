import { api } from "./client";
import type { AuthSession, LoginRequest } from "../types/auth";

export const authApi = {
  session: () => api.get<AuthSession>("/auth/session"),
  login: (request: LoginRequest) =>
    api.post<AuthSession>("/auth/login", request),
  logout: () => api.post<AuthSession>("/auth/logout"),
};
