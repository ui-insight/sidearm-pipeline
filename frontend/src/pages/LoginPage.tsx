import { useState, type FormEvent } from "react";

interface LoginPageProps {
  initialError?: string | null;
  onLogin: (username: string, password: string) => Promise<void>;
}

function errorMessage(error: unknown): string {
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return "Unable to sign in. Try again.";
}

function LoginPage({ initialError, onLogin }: LoginPageProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(initialError ?? null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await onLogin(username.trim(), password);
    } catch (loginError) {
      setError(errorMessage(loginError));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 text-gray-950">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-4 sm:px-6 lg:px-8">
          <span
            aria-hidden="true"
            className="grid size-9 place-items-center bg-gray-950 text-sm font-black text-yellow-400"
          >
            V
          </span>
          <span className="leading-tight">
            <span className="block text-xs font-black uppercase tracking-[0.12em]">
              Vandals
            </span>
            <span className="block text-xs font-medium text-gray-500">
              Stats desk
            </span>
          </span>
        </div>
      </header>

      <main className="mx-auto grid max-w-6xl px-4 py-10 sm:px-6 sm:py-16 lg:grid-cols-[0.9fr_1.1fr] lg:px-8 lg:py-20">
        <section className="bg-gray-950 px-6 py-8 text-gray-100 sm:px-10 sm:py-12 lg:px-12 lg:py-16">
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-yellow-400">
            Restricted prototype
          </p>
          <h1 className="mt-5 max-w-md text-3xl font-bold tracking-tight text-gray-50 sm:text-4xl">
            Verified athletics data, ready for the desk.
          </h1>
          <p className="mt-5 max-w-md text-sm leading-6 text-gray-300">
            Public source material is organized here for internal review,
            historical research, and data-quality decisions.
          </p>
          <dl className="mt-10 grid max-w-md gap-5 border-t border-gray-700 pt-6 text-sm sm:grid-cols-2 lg:grid-cols-1">
            <div>
              <dt className="text-xs font-bold uppercase tracking-[0.1em] text-gray-400">
                Source
              </dt>
              <dd className="mt-1 font-medium text-gray-100">
                GoVandals public records
              </dd>
            </div>
            <div>
              <dt className="text-xs font-bold uppercase tracking-[0.1em] text-gray-400">
                Access
              </dt>
              <dd className="mt-1 font-medium text-gray-100">
                Shared prototype account
              </dd>
            </div>
          </dl>
        </section>

        <section className="border border-t-0 border-gray-200 bg-white px-6 py-8 sm:px-10 sm:py-12 lg:border-l-0 lg:border-t lg:px-14 lg:py-16">
          <div className="max-w-md">
            <p className="text-xs font-bold uppercase tracking-[0.12em] text-gray-500">
              Prototype access
            </p>
            <h2 className="mt-3 text-2xl font-bold tracking-tight">
              Sign in to the stats desk
            </h2>
            <p className="mt-3 text-sm leading-6 text-gray-600">
              Use the shared credentials provided by the project team.
            </p>

            <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
              {error ? (
                <p
                  role="alert"
                  className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-800"
                >
                  {error}
                </p>
              ) : null}

              <div>
                <label
                  htmlFor="prototype-username"
                  className="block text-sm font-semibold text-gray-800"
                >
                  Username
                </label>
                <input
                  id="prototype-username"
                  name="username"
                  type="text"
                  autoComplete="username"
                  autoFocus
                  required
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  className="mt-2 w-full rounded-md border border-gray-300 bg-white px-3 py-2.5 text-sm shadow-sm outline-none transition focus:border-gray-950 focus:ring-2 focus:ring-yellow-400 focus:ring-offset-2"
                />
              </div>

              <div>
                <label
                  htmlFor="prototype-password"
                  className="block text-sm font-semibold text-gray-800"
                >
                  Password
                </label>
                <input
                  id="prototype-password"
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  className="mt-2 w-full rounded-md border border-gray-300 bg-white px-3 py-2.5 text-sm shadow-sm outline-none transition focus:border-gray-950 focus:ring-2 focus:ring-yellow-400 focus:ring-offset-2"
                />
              </div>

              <button
                type="submit"
                disabled={isSubmitting || !username.trim() || !password}
                className="inline-flex min-h-10 w-full items-center justify-center rounded-md bg-yellow-400 px-4 py-2 text-sm font-bold text-gray-950 transition-colors hover:bg-yellow-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500 disabled:cursor-not-allowed disabled:bg-gray-200 disabled:text-gray-500"
              >
                {isSubmitting ? "Signing in…" : "Sign in"}
              </button>
            </form>
          </div>
        </section>
      </main>
    </div>
  );
}

export default LoginPage;
