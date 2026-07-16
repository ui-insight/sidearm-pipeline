import { useEffect, useState, type ReactNode } from "react";
import { authApi } from "../api/auth";
import { setAuthFailureHandler } from "../api/client";
import LoginPage from "../pages/LoginPage";
import type { AuthSession } from "../types/auth";

interface AuthenticatedView {
  username: string;
  logoutPending: boolean;
  logoutError: string | null;
  onLogout: () => Promise<void>;
}

interface AuthenticationBoundaryProps {
  children: (view: AuthenticatedView) => ReactNode;
}

function AuthenticationBoundary({ children }: AuthenticationBoundaryProps) {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [isChecking, setIsChecking] = useState(true);
  const [logoutPending, setLogoutPending] = useState(false);
  const [logoutError, setLogoutError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    setAuthFailureHandler(() => {
      if (active) {
        setSession({ authenticated: false, username: null });
        setSessionError("Your session ended. Sign in again to continue.");
      }
    });

    authApi
      .session()
      .then((currentSession) => {
        if (active) {
          setSession(currentSession);
        }
      })
      .catch(() => {
        if (active) {
          setSession({ authenticated: false, username: null });
          setSessionError("Unable to verify access. Try signing in.");
        }
      })
      .finally(() => {
        if (active) {
          setIsChecking(false);
        }
      });

    return () => {
      active = false;
      setAuthFailureHandler(undefined);
    };
  }, []);

  async function login(username: string, password: string) {
    const authenticatedSession = await authApi.login({ username, password });
    setSessionError(null);
    setSession(authenticatedSession);
  }

  async function logout() {
    setLogoutPending(true);
    setLogoutError(null);
    try {
      await authApi.logout();
      setSessionError(null);
      setSession({ authenticated: false, username: null });
    } catch {
      setLogoutError("Unable to sign out. Check the connection and try again.");
    } finally {
      setLogoutPending(false);
    }
  }

  if (isChecking) {
    return (
      <div className="grid min-h-screen place-items-center bg-gray-50 px-4 text-gray-950">
        <div className="flex items-center gap-3" role="status">
          <span
            aria-hidden="true"
            className="grid size-9 place-items-center bg-gray-950 text-sm font-black text-yellow-400"
          >
            V
          </span>
          <span className="text-sm font-semibold text-gray-600">
            Checking access…
          </span>
        </div>
      </div>
    );
  }

  if (!session?.authenticated) {
    return <LoginPage initialError={sessionError} onLogin={login} />;
  }

  return children({
    username: session.username ?? "Prototype user",
    logoutPending,
    logoutError,
    onLogout: logout,
  });
}

export default AuthenticationBoundary;
