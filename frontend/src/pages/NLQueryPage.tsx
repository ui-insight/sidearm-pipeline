import { useState } from "react";
import { nlQueryApi } from "../api/agentRuns";
import { ApiError } from "../api/client";
import type { NLQueryResult } from "../types/agentRun";

function NLQueryPage() {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<NLQueryResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sqlExpanded, setSqlExpanded] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const q = question.trim();
    if (!q) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setSqlExpanded(false);
    try {
      const res = await nlQueryApi.query(q);
      setResult(res);
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? typeof err.data === "object" && err.data && "detail" in err.data
            ? String(err.data.detail)
            : err.message
          : err instanceof Error
            ? err.message
            : "Query failed";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-6 py-10">
      <header className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">
          Natural Language Query
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          Ask questions about the games database in plain English.
        </p>
      </header>

      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 mb-6">
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <textarea
            rows={4}
            maxLength={500}
            required
            placeholder="How many games have been ingested? Which team has the most points scored?"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-yellow-400 focus:border-yellow-400 resize-none"
          />
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-400">{question.length}/500</span>
            <button
              type="submit"
              disabled={loading || question.trim().length === 0}
              className="bg-yellow-400 hover:bg-yellow-500 disabled:opacity-50 text-gray-950 font-semibold px-4 py-2 rounded-lg text-sm transition"
            >
              {loading ? "Querying…" : "Ask"}
            </button>
          </div>
        </form>
      </div>

      {error && (
        <div className="mb-6 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
          {error}
        </div>
      )}

      {result && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 space-y-5">
          <div>
            <p className="text-xs uppercase tracking-wide text-gray-500 mb-1">
              Question
            </p>
            <p className="text-gray-900">{result.question}</p>
          </div>

          {result.answer && (
            <div>
              <p className="text-xs uppercase tracking-wide text-gray-500 mb-1">
                Answer
              </p>
              <p className="text-base text-gray-900 leading-relaxed">{result.answer}</p>
            </div>
          )}

          {result.sql && (
            <div>
              <button
                onClick={() => setSqlExpanded((v) => !v)}
                className="text-xs uppercase tracking-wide text-gray-500 hover:text-gray-900 flex items-center gap-1"
              >
                SQL {sqlExpanded ? "▲" : "▼"}
              </button>
              {sqlExpanded && (
                <pre className="mt-2 text-xs font-mono bg-gray-50 border border-gray-200 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap">
                  {result.sql}
                </pre>
              )}
            </div>
          )}

          {result.rows.length > 0 && (
            <div>
              <p className="text-xs uppercase tracking-wide text-gray-500 mb-2">
                Raw rows ({result.rows.length})
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-xs border border-gray-200 rounded-lg overflow-hidden">
                  <thead>
                    <tr className="bg-gray-50 border-b border-gray-200">
                      {Object.keys(result.rows[0] ?? {}).map((col) => (
                        <th
                          key={col}
                          className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-gray-500"
                        >
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {result.rows.map((row, i) => (
                      <tr
                        key={i}
                        className="border-t border-gray-100 even:bg-gray-50"
                      >
                        {Object.values(row).map((val, j) => (
                          <td
                            key={j}
                            className="px-3 py-2 text-gray-700 font-mono"
                          >
                            {val == null ? (
                              <span className="text-gray-400">null</span>
                            ) : (
                              String(val)
                            )}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <p className="text-xs text-gray-400 pt-2 border-t border-gray-100">
            Agent run #{result.agent_run_id}
          </p>
        </div>
      )}
    </div>
  );
}

export default NLQueryPage;
