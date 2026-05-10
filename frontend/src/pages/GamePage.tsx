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
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-900">
              {game.away_team ?? "Away"} at {game.home_team ?? "Home"}
            </h1>
            <PublishStatusBadge status={game.publish_status} />
          </div>
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

        <CoverageReviewPanel
          gameId={game.id}
          approvedContent={game.generated_content[0] ?? null}
          onContentApproved={handleContentApproved}
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
