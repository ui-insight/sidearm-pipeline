import { useState, type FormEvent } from "react";
import { ApiError } from "../api/client";
import { semanticQueriesApi } from "../api/semanticQueries";
import type { SemanticQuestionAnswer } from "../types/semanticQuery";

const EXAMPLE_QUESTIONS = [
  "What was Idaho's record in 2025-26?",
  "Who led Idaho in points in 2025-26?",
  "Who are Idaho's career leaders in rebounds?",
];

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "The question could not be answered.";
}

function labelForKey(key: string): string {
  return key.replace(/_/g, " ");
}

function formatParameter(value: unknown): string {
  if (value === null) return "Not set";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
}

function AskWarehousePage() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<SemanticQuestionAnswer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submitQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = question.trim();
    if (normalized.length < 3) {
      setError("Enter a question with at least 3 characters.");
      return;
    }
    setLoading(true);
    setError(null);
    setAnswer(null);
    try {
      setAnswer(await semanticQueriesApi.ask(normalized));
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8 lg:py-12">
      <header className="max-w-3xl">
        <p className="text-xs font-bold uppercase tracking-[0.12em] text-yellow-700">
          SID research desk
        </p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-gray-950">
          Ask the warehouse
        </h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-gray-600">
          Ask about verified women&apos;s basketball records, leaders, player
          totals, and game splits. Every answer stays attached to the query and
          warehouse evidence behind it.
        </p>
      </header>

      <form
        onSubmit={(event) => void submitQuestion(event)}
        className="mt-8 border-y border-gray-200 bg-white px-5 py-6 sm:px-7"
      >
        <label htmlFor="warehouse-question" className="text-sm font-semibold text-gray-950">
          What do you need to know?
        </label>
        <textarea
          id="warehouse-question"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          rows={3}
          maxLength={500}
          placeholder="Example: Who led Idaho in points in 2025-26?"
          className="mt-3 block w-full resize-y rounded-md border border-gray-300 bg-white px-3 py-3 text-base text-gray-950 shadow-sm outline-none placeholder:text-gray-400 focus:border-gray-950 focus:ring-2 focus:ring-yellow-500 focus:ring-offset-2"
        />
        <div className="mt-4 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.08em] text-gray-500">
              Try an example
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              {EXAMPLE_QUESTIONS.map((example) => (
                <button
                  key={example}
                  type="button"
                  onClick={() => setQuestion(example)}
                  className="rounded-full border border-gray-300 bg-gray-50 px-3 py-1.5 text-left text-xs font-medium text-gray-700 transition-colors hover:border-gray-500 hover:bg-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500"
                >
                  {example}
                </button>
              ))}
            </div>
          </div>
          <button
            type="submit"
            disabled={loading}
            className="shrink-0 rounded-md bg-gray-950 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-gray-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500 disabled:cursor-wait disabled:bg-gray-400"
          >
            {loading ? "Checking verified data…" : "Ask question"}
          </button>
        </div>
      </form>

      {error ? (
        <div role="alert" className="mt-6 border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-900">
          <p className="font-semibold">The research request failed</p>
          <p className="mt-1">{error}</p>
        </div>
      ) : null}

      {loading ? (
        <div role="status" aria-label="Researching question" className="mt-8 animate-pulse border-y border-gray-200 bg-white px-5 py-7 sm:px-7">
          <div className="h-3 w-28 rounded bg-gray-200" />
          <div className="mt-5 h-6 max-w-2xl rounded bg-gray-200" />
          <div className="mt-3 h-4 max-w-xl rounded bg-gray-100" />
          <span className="sr-only">Researching question</span>
        </div>
      ) : null}

      {answer ? (
        <article className="mt-8 border-y border-gray-200 bg-white">
          <div className="px-5 py-7 sm:px-7">
            <div className="flex flex-wrap items-center gap-3">
              <span className={answer.status === "answered" ? "rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-bold uppercase tracking-[0.08em] text-emerald-800" : "rounded-full bg-amber-50 px-2.5 py-1 text-xs font-bold uppercase tracking-[0.08em] text-amber-800"}>
                {answer.status === "answered" ? "Verified answer" : "Outside catalog"}
              </span>
              <span className="text-xs text-gray-500">{answer.model}</span>
            </div>
            <h2 className="mt-4 text-sm font-semibold text-gray-500">{answer.question}</h2>
            <p className="mt-2 max-w-3xl text-xl font-semibold leading-8 text-gray-950">
              {answer.answer}
            </p>
          </div>

          {answer.query && answer.result ? (
            <div className="border-t border-gray-200 bg-gray-50 px-5 py-6 sm:px-7">
              <h3 className="text-lg font-semibold text-gray-950">Evidence trail</h3>
              <p className="mt-1 text-sm text-gray-600">
                Review the catalog query and returned rows before using the answer in published copy.
              </p>
              <dl className="mt-5 grid gap-x-8 gap-y-4 sm:grid-cols-2 lg:grid-cols-3">
                {Object.entries(answer.query).map(([key, value]) => (
                  <div key={key}>
                    <dt className="text-xs font-bold uppercase tracking-[0.08em] text-gray-500">
                      {labelForKey(key)}
                    </dt>
                    <dd className="mt-1 font-mono text-sm text-gray-950">
                      {formatParameter(value)}
                    </dd>
                  </div>
                ))}
              </dl>
              <details className="mt-6 border-t border-gray-300 pt-4">
                <summary className="cursor-pointer text-sm font-semibold text-gray-950 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500">
                  View underlying warehouse result
                </summary>
                <pre className="mt-4 max-h-[32rem] overflow-auto rounded-md bg-gray-950 p-4 text-xs leading-5 text-gray-100">
                  {JSON.stringify(answer.result, null, 2)}
                </pre>
              </details>
            </div>
          ) : null}
        </article>
      ) : null}
    </div>
  );
}

export default AskWarehousePage;
