import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { gamesApi } from "../api/games";
import { ApiError } from "../api/client";
import type { GameDetail, GeneratedContent, PlayerStatGroup } from "../types/game";

const CATEGORY_LABELS: Record<string, string> = {
  passing: "Passing",
  rushing: "Rushing",
  receiving: "Receiving",
  defense: "Defense",
  kicking: "Kicking",
  punting: "Punting",
  returns: "Returns",
  kick_returns: "Kick Returns",
  punt_returns: "Punt Returns",
  interceptions: "Interceptions",
};

function categoryLabel(category: string): string {
  return CATEGORY_LABELS[category] ?? category;
}

function GamePage() {
  const { id } = useParams<{ id: string }>();
  const [game, setGame] = useState<GameDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    gamesApi
      .get(Number(id))
      .then(setGame)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load game"),
      );
  }, [id]);

  async function handleGenerate() {
    if (!game) return;
    setGenError(null);
    setGenerating(true);
    try {
      const newContent = await gamesApi.generate(game.id);
      setGame({
        ...game,
        generated_content: [newContent, ...game.generated_content],
      });
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? typeof err.data === "object" && err.data && "detail" in err.data
            ? String(err.data.detail)
            : err.message
          : err instanceof Error
            ? err.message
            : "Generation failed";
      setGenError(msg);
    } finally {
      setGenerating(false);
    }
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <p className="text-red-700">{error}</p>
          <Link to="/" className="text-sm text-yellow-700 hover:underline mt-2 inline-block">
            Back to list
          </Link>
        </div>
      </div>
    );
  }

  if (!game) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <p className="text-gray-500">Loading…</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-5xl mx-auto px-6 py-10">
        <Link to="/" className="text-sm text-gray-600 hover:text-yellow-700">
          ← All games
        </Link>

        <header className="mt-4 mb-6">
          <h1 className="text-2xl font-bold text-gray-900">
            {game.away_team ?? "Away"} at {game.home_team ?? "Home"}
          </h1>
          <p className="text-sm text-gray-600 mt-1">
            {game.sport && <span className="uppercase mr-2">{game.sport}</span>}
            {game.game_date ?? ""} · Season {game.season}
          </p>
          <p className="text-4xl font-mono tabular-nums mt-3 text-gray-900">
            {game.away_score ?? "—"} <span className="text-gray-400">–</span>{" "}
            {game.home_score ?? "—"}
          </p>
          <a
            href={game.source_url}
            target="_blank"
            rel="noreferrer"
            className="text-xs text-gray-500 hover:text-yellow-700 break-all"
          >
            {game.source_url}
          </a>
        </header>

        <CoverageSection
          content={game.generated_content[0] ?? null}
          history={game.generated_content.slice(1)}
          generating={generating}
          onGenerate={handleGenerate}
          error={genError}
        />

        {game.scoring_plays.length > 0 && (
          <Section title="Scoring Summary">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left text-xs uppercase text-gray-500">
                  <th className="py-2 pr-3">Qtr</th>
                  <th className="py-2 pr-3">Time</th>
                  <th className="py-2 pr-3">Team</th>
                  <th className="py-2 pr-3">Play</th>
                  <th className="py-2 text-right">Score</th>
                </tr>
              </thead>
              <tbody>
                {game.scoring_plays.map((play, i) => (
                  <tr key={i} className="border-b border-gray-100 last:border-0">
                    <td className="py-2 pr-3 font-mono">{play.period}</td>
                    <td className="py-2 pr-3 font-mono">{play.clock}</td>
                    <td className="py-2 pr-3 font-medium">{play.team}</td>
                    <td className="py-2 pr-3 text-gray-700">{play.description}</td>
                    <td className="py-2 text-right font-mono tabular-nums">
                      {play.away_score}-{play.home_score}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Section>
        )}

        {game.team_stats.length > 0 && (
          <Section title="Team Stats">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left text-xs uppercase text-gray-500">
                  <th className="py-2 pr-3">Statistic</th>
                  <th className="py-2 text-right">{game.home_team ?? "Home"}</th>
                  <th className="py-2 text-right">{game.away_team ?? "Away"}</th>
                </tr>
              </thead>
              <tbody>
                {game.team_stats.map((stat, i) => (
                  <tr key={i} className="border-b border-gray-100 last:border-0">
                    <td className="py-1.5 pr-3 text-gray-700">{stat.stat_name}</td>
                    <td className="py-1.5 text-right font-mono tabular-nums">
                      {stat.home_value}
                    </td>
                    <td className="py-1.5 text-right font-mono tabular-nums">
                      {stat.away_value}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Section>
        )}

        {game.player_stats.length > 0 && (
          <Section title="Individual Stats">
            <div className="space-y-6">
              {game.player_stats.map((group, i) => (
                <PlayerStatTable key={i} group={group} />
              ))}
            </div>
          </Section>
        )}
      </div>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="bg-white rounded-lg shadow-sm p-6 mb-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">{title}</h2>
      {children}
    </section>
  );
}

function CoverageSection({
  content,
  history,
  generating,
  onGenerate,
  error,
}: {
  content: GeneratedContent | null;
  history: GeneratedContent[];
  generating: boolean;
  onGenerate: () => void;
  error: string | null;
}) {
  return (
    <section className="bg-white rounded-lg shadow-sm p-6 mb-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">
            AI Coverage
          </h2>
          <p className="text-xs text-gray-500 mt-0.5">
            Generated from the boxscore above using Claude.
          </p>
        </div>
        <button
          onClick={onGenerate}
          disabled={generating}
          className="bg-gray-900 hover:bg-gray-800 disabled:opacity-50 text-white font-medium px-4 py-2 rounded-md text-sm transition"
        >
          {generating
            ? "Generating…"
            : content
              ? "Regenerate"
              : "Generate Coverage"}
        </button>
      </div>

      {error && (
        <p className="mb-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">
          {error}
        </p>
      )}

      {!content && !generating && !error && (
        <p className="text-sm text-gray-500">
          No coverage yet. Click the button to produce a headline, recap,
          player spotlight, and social post from this boxscore.
        </p>
      )}

      {content && (
        <div className="space-y-6">
          {content.headline && (
            <div>
              <Label>Headline</Label>
              <p className="text-xl font-bold text-gray-900 leading-snug">
                {content.headline}
              </p>
            </div>
          )}

          <CopyableBlock label="Recap" text={content.recap}>
            {content.recap.split(/\n\n+/).map((para, i) => (
              <p key={i} className="text-gray-800 leading-relaxed mb-3 last:mb-0">
                {para}
              </p>
            ))}
          </CopyableBlock>

          <CopyableBlock
            label={`Player Spotlight${content.spotlight_player ? ` — ${content.spotlight_player}` : ""}`}
            text={content.spotlight_body}
          >
            <p className="text-gray-800 leading-relaxed">
              {content.spotlight_body}
            </p>
          </CopyableBlock>

          <CopyableBlock label="Social Post" text={content.social_post}>
            <p className="text-gray-800 leading-relaxed font-mono text-sm bg-gray-50 rounded p-3 border border-gray-200">
              {content.social_post}
            </p>
            <p className="text-xs text-gray-400 mt-1">
              {content.social_post.length} chars
            </p>
          </CopyableBlock>

          <p className="text-xs text-gray-400 pt-2 border-t border-gray-100">
            Generated {new Date(content.generated_at).toLocaleString()}
            {content.model && ` · ${content.model}`}
            {history.length > 0 && ` · ${history.length} earlier version${history.length === 1 ? "" : "s"}`}
          </p>
        </div>
      )}
    </section>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-xs uppercase tracking-wide text-gray-500 mb-1">
      {children}
    </p>
  );
}

function CopyableBlock({
  label,
  text,
  children,
}: {
  label: string;
  text: string;
  children: React.ReactNode;
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div>
      <div className="flex items-baseline justify-between mb-1">
        <Label>{label}</Label>
        <button
          onClick={copy}
          className="text-xs text-gray-500 hover:text-gray-900"
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      {children}
    </div>
  );
}

function PlayerStatTable({ group }: { group: PlayerStatGroup }) {
  return (
    <div>
      <h3 className="text-sm font-semibold text-gray-700 mb-2">
        {categoryLabel(group.category)}
      </h3>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200 text-left text-xs uppercase text-gray-500">
            {group.columns.map((col, i) => (
              <th
                key={i}
                className={i === 0 ? "py-2 pr-3" : "py-2 pr-3 text-right"}
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {group.rows.map((row, i) => (
            <tr key={i} className="border-b border-gray-100 last:border-0">
              {row.map((cell, j) => (
                <td
                  key={j}
                  className={
                    j === 0
                      ? "py-1.5 pr-3 text-gray-900"
                      : "py-1.5 pr-3 text-right font-mono tabular-nums text-gray-700"
                  }
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default GamePage;
