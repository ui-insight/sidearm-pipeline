import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { gamesApi } from "../api/games";
import CoverageReviewPanel from "../components/CoverageReviewPanel";
import PublishStatusBadge from "../components/PublishStatusBadge";
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
  const [reingesting, setReingesting] = useState(false);
  const [reingestError, setReingestError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    gamesApi
      .get(Number(id))
      .then(setGame)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load game"),
      );
  }, [id]);

  function handleContentApproved(content: GeneratedContent) {
    if (!game) return;
    setGame({
      ...game,
      generated_content: [content, ...game.generated_content],
    });
  }

  async function handleReingest() {
    if (!game) return;
    setReingesting(true);
    setReingestError(null);
    try {
      const updated = await gamesApi.reingest(game.id);
      setGame(updated);
    } catch (err) {
      setReingestError(err instanceof Error ? err.message : "Re-ingest failed");
    } finally {
      setReingesting(false);
    }
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-24">
        <div className="text-center">
          <p className="text-red-700 mb-2">{error}</p>
          <Link to="/" className="text-sm text-gray-500 hover:text-gray-900">
            ← Games
          </Link>
        </div>
      </div>
    );
  }

  if (!game) {
    return (
      <div className="flex items-center justify-center py-24">
        <p className="text-gray-500">Loading…</p>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-10">
      <Link to="/" className="text-sm text-gray-500 hover:text-gray-900 transition-colors">
        ← Games
      </Link>

      <header className="mt-4 mb-6 bg-white rounded-xl border border-gray-200 shadow-sm p-6">
        <div className="flex items-center gap-3 mb-1">
          {game.sport && (
            <span className="text-xs font-semibold uppercase tracking-wide text-yellow-600 bg-yellow-50 px-2 py-0.5 rounded">
              {game.sport}
            </span>
          )}
          <span className="text-xs text-gray-500">Season {game.season}</span>
          <PublishStatusBadge status={game.publish_status} />
        </div>
        {game.game_date && (
          <p className="text-sm text-gray-500 mb-4">{game.game_date}</p>
        )}

        <div className="flex items-center gap-4">
          <div className="flex-1 text-left">
            <p className="text-lg font-semibold text-gray-700">
              {game.away_team ?? "Away"}
            </p>
          </div>
          <div className="flex-1 text-center">
            <p className="text-5xl font-bold tabular-nums font-mono text-gray-900">
              {game.away_score ?? "—"}
              <span className="text-gray-300 mx-3">–</span>
              {game.home_score ?? "—"}
            </p>
          </div>
          <div className="flex-1 text-right">
            <p className="text-lg font-semibold text-gray-700">
              {game.home_team ?? "Home"}
            </p>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <a
            href={game.source_url}
            target="_blank"
            rel="noreferrer"
            className="text-xs text-gray-400 hover:text-yellow-700 break-all transition-colors"
          >
            {game.source_url}
          </a>
          <button
            type="button"
            onClick={() => void handleReingest()}
            disabled={reingesting}
            className="border border-gray-200 bg-white hover:bg-gray-50 disabled:opacity-50 text-gray-700 font-medium px-4 py-2 rounded-lg text-sm transition"
          >
            {reingesting ? "Re-ingesting…" : "Re-ingest boxscore"}
          </button>
          {reingestError && (
            <span className="text-xs text-red-600">{reingestError}</span>
          )}
        </div>
      </header>

      <CoverageReviewPanel
        gameId={game.id}
        approvedContent={game.generated_content[0] ?? null}
        onContentApproved={handleContentApproved}
      />

      {game.scoring_plays.length > 0 && (
        <Section title="Scoring Summary">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                <th className="px-4 py-3 rounded-tl-lg">Qtr</th>
                <th className="px-4 py-3">Time</th>
                <th className="px-4 py-3">Team</th>
                <th className="px-4 py-3">Play</th>
                <th className="px-4 py-3 text-right rounded-tr-lg">Score</th>
              </tr>
            </thead>
            <tbody>
              {game.scoring_plays.map((play, i) => (
                <tr key={i} className="border-t border-gray-100 even:bg-gray-50">
                  <td className="px-4 py-3 font-mono">{play.period}</td>
                  <td className="px-4 py-3 font-mono">{play.clock}</td>
                  <td className="px-4 py-3 font-medium">{play.team}</td>
                  <td className="px-4 py-3 text-gray-700">{play.description}</td>
                  <td className="px-4 py-3 text-right font-mono tabular-nums">
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
              <tr className="bg-gray-50 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                <th className="px-4 py-3 rounded-tl-lg">Statistic</th>
                <th className="px-4 py-3 text-right">{game.home_team ?? "Home"}</th>
                <th className="px-4 py-3 text-right rounded-tr-lg">{game.away_team ?? "Away"}</th>
              </tr>
            </thead>
            <tbody>
              {game.team_stats.map((stat, i) => (
                <tr key={i} className="border-t border-gray-100 even:bg-gray-50">
                  <td className="px-4 py-3 text-gray-700">{stat.stat_name}</td>
                  <td className="px-4 py-3 text-right font-mono tabular-nums">
                    {stat.home_value}
                  </td>
                  <td className="px-4 py-3 text-right font-mono tabular-nums">
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
    <section className="bg-white rounded-xl border border-gray-200 shadow-sm mb-6 overflow-hidden">
      <h2 className="text-base font-semibold text-gray-900 px-4 py-3 border-b border-gray-100">
        {title}
      </h2>
      <div className="p-4">{children}</div>
    </section>
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
          <tr className="bg-gray-50 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
            {group.columns.map((col, i) => (
              <th
                key={i}
                className={i === 0 ? "px-4 py-2" : "px-4 py-2 text-right"}
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {group.rows.map((row, i) => (
            <tr key={i} className="border-t border-gray-100 even:bg-gray-50">
              {row.map((cell, j) => (
                <td
                  key={j}
                  className={
                    j === 0
                      ? "px-4 py-2 text-gray-900"
                      : "px-4 py-2 text-right font-mono tabular-nums text-gray-700"
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
