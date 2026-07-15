import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../api/client";
import { gamesApi } from "../api/games";
import type {
  GameDetail,
  GeneratedContent,
  NormalizedPlayerGameStat,
  PlayerStatGroup,
} from "../types/game";

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

interface NormalizedPlayerRow {
  playerId: number;
  playerName: string;
  teamName: string | null;
  facts: Map<string, NormalizedPlayerGameStat>;
}

function categoryLabel(category: string): string {
  return CATEGORY_LABELS[category] ?? category;
}

function humanPlayerName(value: string): string {
  if (!value.includes(",")) return value;
  const [lastName, ...rest] = value.split(",");
  return `${rest.join(",").trim()} ${(lastName ?? "").trim()}`.trim();
}

function normalizedRows(facts: NormalizedPlayerGameStat[]): NormalizedPlayerRow[] {
  const rows = new Map<number, NormalizedPlayerRow>();
  for (const fact of facts) {
    const existing = rows.get(fact.player_id) ?? {
      playerId: fact.player_id,
      playerName: humanPlayerName(fact.player_name),
      teamName: fact.team_name,
      facts: new Map<string, NormalizedPlayerGameStat>(),
    };
    existing.facts.set(fact.stat_key, fact);
    rows.set(fact.player_id, existing);
  }
  return Array.from(rows.values()).sort((left, right) =>
    left.playerName.localeCompare(right.playerName),
  );
}

function atomicValue(row: NormalizedPlayerRow, statKey: string): string {
  const fact = row.facts.get(statKey);
  if (!fact) return "-";
  if (statKey === "minutes_played" && fact.source_value) {
    return fact.source_value;
  }
  const numericValue = Number(fact.value);
  return Number.isInteger(numericValue) ? String(numericValue) : String(fact.value);
}

function sourceComposite(
  row: NormalizedPlayerRow,
  madeKey: string,
  attemptedKey: string,
): string {
  const made = row.facts.get(madeKey);
  if (made?.source_value?.includes("-")) return made.source_value;
  return `${atomicValue(row, madeKey)}-${atomicValue(row, attemptedKey)}`;
}

function apiErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    if (typeof error.data === "object" && error.data && "detail" in error.data) {
      return String(error.data.detail);
    }
    return error.message;
  }
  return error instanceof Error ? error.message : fallback;
}

function GamePage() {
  const { id } = useParams<{ id: string }>();
  const [game, setGame] = useState<GameDetail | null>(null);
  const [facts, setFacts] = useState<NormalizedPlayerGameStat[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [factsError, setFactsError] = useState<string | null>(null);
  const [factsLoading, setFactsLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let active = true;
    const gameId = Number(id);

    gamesApi
      .get(gameId)
      .then((loadedGame) => {
        if (active) setGame(loadedGame);
      })
      .catch((loadError) => {
        if (active) {
          setError(apiErrorMessage(loadError, "Failed to load game"));
        }
      });

    gamesApi
      .playerStats(gameId)
      .then((loadedFacts) => {
        if (active) setFacts(loadedFacts);
      })
      .catch((loadError) => {
        if (active) {
          setFactsError(
            apiErrorMessage(loadError, "Failed to load normalized player facts"),
          );
        }
      })
      .finally(() => {
        if (active) setFactsLoading(false);
      });

    return () => {
      active = false;
    };
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
    } catch (generateError) {
      setGenError(apiErrorMessage(generateError, "Generation failed"));
    } finally {
      setGenerating(false);
    }
  }

  if (error) {
    return (
      <div className="grid min-h-[60vh] place-items-center px-6">
        <div className="max-w-md text-center">
          <p className="text-sm font-semibold text-red-800">{error}</p>
          <Link
            to="/"
            className="mt-3 inline-block text-sm font-medium text-gray-950 underline decoration-gray-300 underline-offset-4 hover:decoration-yellow-500 focus-visible:rounded-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500"
          >
            Back to games
          </Link>
        </div>
      </div>
    );
  }

  if (!game) return <GamePageSkeleton />;

  const latestSnapshot = [...game.source_snapshots].sort(
    (left, right) =>
      new Date(right.fetched_at).getTime() - new Date(left.fetched_at).getTime(),
  )[0];
  const rows = normalizedRows(facts);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
      <Link
        to="/"
        className="text-sm font-medium text-gray-600 underline decoration-gray-300 underline-offset-4 hover:text-gray-950 hover:decoration-yellow-500 focus-visible:rounded-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500"
      >
        Back to games
      </Link>

      <header className="mt-5 border-y border-gray-300 bg-white">
        <div className="flex flex-col gap-6 px-5 py-6 sm:px-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.08em] text-gray-500">
              <span>{game.sport_name ?? game.sport ?? "Athletics"}</span>
              <span aria-hidden="true">/</span>
              <span>{game.game_date ?? "Date unavailable"}</span>
              {game.season && (
                <>
                  <span aria-hidden="true">/</span>
                  <span>{game.season}</span>
                </>
              )}
            </div>
            <h1 className="mt-3 text-2xl font-bold tracking-tight text-gray-950 sm:text-3xl">
              {game.away_team ?? "Away"} at {game.home_team ?? "Home"}
            </h1>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <StatusChip label={game.event_status} />
              <StatusChip label={game.publish_status} quiet />
              {game.conference_event && <StatusChip label="conference" quiet />}
            </div>
          </div>

          <div
            className="grid grid-cols-[minmax(7rem,1fr)_auto_minmax(7rem,1fr)] items-end gap-3 sm:gap-5"
            aria-label={`${game.away_team ?? "Away"} ${game.away_score ?? "no score"}, ${game.home_team ?? "Home"} ${game.home_score ?? "no score"}`}
          >
            <div className="text-right">
              <p className="truncate text-xs font-semibold uppercase tracking-wide text-gray-500">
                {game.away_team ?? "Away"}
              </p>
              <p className="mt-1 font-mono text-4xl font-semibold tabular-nums text-gray-950">
                {game.away_score ?? "-"}
              </p>
            </div>
            <span className="pb-2 text-xs font-semibold uppercase text-gray-400">Final</span>
            <div>
              <p className="truncate text-xs font-semibold uppercase tracking-wide text-gray-500">
                {game.home_team ?? "Home"}
              </p>
              <p className="mt-1 font-mono text-4xl font-semibold tabular-nums text-gray-950">
                {game.home_score ?? "-"}
              </p>
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-2 border-t border-gray-200 bg-gray-50 px-5 py-3 text-xs text-gray-600 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <p>
            <span className="font-semibold text-gray-800">Source evidence:</span>{" "}
            {latestSnapshot
              ? `${latestSnapshot.source_system} ${latestSnapshot.source_type.replace(/_/g, " ")}, fetched ${new Date(latestSnapshot.fetched_at).toLocaleString()}`
              : "No source snapshot retained"}
          </p>
          <a
            href={game.source_url}
            target="_blank"
            rel="noreferrer"
            className="shrink-0 font-semibold text-gray-900 underline decoration-gray-300 underline-offset-2 hover:decoration-yellow-500 focus-visible:rounded-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500"
          >
            Open original boxscore
          </a>
        </div>
      </header>

      <div className="mt-6 grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="min-w-0">
          {(factsLoading || factsError || rows.length > 0 || game.sport === "womens-basketball") && (
            <NormalizedStatsSection
              rows={rows}
              facts={facts}
              loading={factsLoading}
              error={factsError}
              latestSnapshotId={latestSnapshot?.id ?? null}
            />
          )}

          {game.scoring_plays.length > 0 && (
            <Section title="Scoring summary">
              <div className="overflow-x-auto" tabIndex={0}>
                <table className="w-full min-w-[40rem] text-sm">
                  <thead>
                    <tr className="border-b border-gray-300 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                      <th scope="col" className="py-2 pr-3">Qtr</th>
                      <th scope="col" className="py-2 pr-3">Time</th>
                      <th scope="col" className="py-2 pr-3">Team</th>
                      <th scope="col" className="py-2 pr-3">Play</th>
                      <th scope="col" className="py-2 text-right">Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {game.scoring_plays.map((play, index) => (
                      <tr key={index} className="border-b border-gray-100 last:border-0">
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
              </div>
            </Section>
          )}

          {game.team_stats.length > 0 && (
            <Section title="Team stats">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-300 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                    <th scope="col" className="py-2 pr-3">Statistic</th>
                    <th scope="col" className="py-2 text-right">{game.home_team ?? "Home"}</th>
                    <th scope="col" className="py-2 text-right">{game.away_team ?? "Away"}</th>
                  </tr>
                </thead>
                <tbody>
                  {game.team_stats.map((stat, index) => (
                    <tr key={index} className="border-b border-gray-100 last:border-0">
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

          {rows.length === 0 && game.player_stats.length > 0 && (
            <Section title="Individual stats">
              <div className="space-y-6">
                {game.player_stats.map((group, index) => (
                  <PlayerStatTable key={index} group={group} />
                ))}
              </div>
            </Section>
          )}
        </div>

        <div className="xl:sticky xl:top-6">
          <CoverageSection
            content={game.generated_content[0] ?? null}
            history={game.generated_content.slice(1)}
            generating={generating}
            onGenerate={handleGenerate}
            error={genError}
          />
        </div>
      </div>
    </div>
  );
}

function GamePageSkeleton() {
  return (
    <div className="mx-auto max-w-7xl animate-pulse px-4 py-10 sm:px-6 lg:px-8" aria-label="Loading game">
      <div className="h-4 w-24 rounded bg-gray-200" />
      <div className="mt-5 border-y border-gray-200 bg-white px-6 py-8">
        <div className="h-3 w-48 rounded bg-gray-200" />
        <div className="mt-4 h-8 w-96 max-w-full rounded bg-gray-200" />
        <div className="mt-5 h-12 w-52 rounded bg-gray-100" />
      </div>
      <div className="mt-6 h-80 rounded-lg border border-gray-200 bg-white" />
    </div>
  );
}

function StatusChip({ label, quiet = false }: { label: string; quiet?: boolean }) {
  return (
    <span
      className={`rounded-full border px-2 py-0.5 text-xs font-semibold capitalize ${
        quiet
          ? "border-gray-200 bg-gray-50 text-gray-600"
          : "border-yellow-200 bg-yellow-50 text-yellow-800"
      }`}
    >
      {label.replace(/_/g, " ")}
    </span>
  );
}

function NormalizedStatsSection({
  rows,
  facts,
  loading,
  error,
  latestSnapshotId,
}: {
  rows: NormalizedPlayerRow[];
  facts: NormalizedPlayerGameStat[];
  loading: boolean;
  error: string | null;
  latestSnapshotId: number | null;
}) {
  const snapshotIds = new Set(
    facts
      .map((fact) => fact.source_snapshot_id)
      .filter((snapshotId): snapshotId is number => snapshotId !== null),
  );
  const isLatestSnapshot =
    latestSnapshotId !== null && snapshotIds.size === 1 && snapshotIds.has(latestSnapshotId);

  return (
    <section className="mb-6 overflow-hidden rounded-lg border border-gray-200 bg-white">
      <div className="flex flex-col gap-2 border-b border-gray-200 px-5 py-4 sm:flex-row sm:items-start sm:justify-between sm:px-6">
        <div>
          <h2 className="text-lg font-semibold text-gray-950">Normalized player stats</h2>
          <p className="mt-0.5 text-xs leading-5 text-gray-500">
            Canonical player identities and atomic, provenance-aware game facts.
          </p>
        </div>
        {!loading && rows.length > 0 && (
          <div className="shrink-0 text-xs text-gray-500 sm:text-right">
            <span className="block">{rows.length} players / {facts.length} facts</span>
            <span className="mt-1 block sm:hidden">Scroll table for every column</span>
          </div>
        )}
      </div>

      {loading ? (
        <div className="animate-pulse space-y-3 px-6 py-6" aria-label="Loading normalized player stats">
          <div className="h-4 w-full rounded bg-gray-100" />
          <div className="h-4 w-11/12 rounded bg-gray-100" />
          <div className="h-4 w-10/12 rounded bg-gray-100" />
        </div>
      ) : error ? (
        <p role="alert" className="m-5 border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </p>
      ) : rows.length === 0 ? (
        <div className="px-6 py-10 text-center">
          <p className="text-sm font-semibold text-gray-950">No normalized player facts yet</p>
          <p className="mx-auto mt-1 max-w-xl text-sm text-gray-500">
            Reingest this women&apos;s basketball boxscore after roster identities are available.
          </p>
        </div>
      ) : (
        <>
          <div
            className="overflow-x-auto focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-yellow-500"
            tabIndex={0}
            aria-label="Scrollable normalized player statistics"
          >
            <table className="w-full min-w-[52rem] text-sm">
              <thead>
                <tr className="border-b border-gray-300 bg-gray-50 text-xs font-semibold uppercase tracking-wide text-gray-500">
                  <th scope="col" className="sticky left-0 bg-gray-50 px-5 py-2.5 text-left sm:px-6">Player</th>
                  <StatHeading>MIN</StatHeading>
                  <StatHeading>FG</StatHeading>
                  <StatHeading>3PT</StatHeading>
                  <StatHeading>FT</StatHeading>
                  <StatHeading>REB</StatHeading>
                  <StatHeading>A</StatHeading>
                  <StatHeading>TO</StatHeading>
                  <StatHeading>BLK</StatHeading>
                  <StatHeading>STL</StatHeading>
                  <StatHeading strong>PTS</StatHeading>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.playerId} className="group border-b border-gray-100 last:border-0 hover:bg-yellow-50/40">
                    <th
                      scope="row"
                      className="sticky left-0 bg-white px-5 py-2.5 text-left font-medium text-gray-950 group-hover:bg-yellow-50 sm:px-6"
                    >
                      {row.playerName}
                    </th>
                    <StatCell>{atomicValue(row, "minutes_played")}</StatCell>
                    <StatCell>{sourceComposite(row, "field_goals_made", "field_goals_attempted")}</StatCell>
                    <StatCell>{sourceComposite(row, "three_point_field_goals_made", "three_point_field_goals_attempted")}</StatCell>
                    <StatCell>{sourceComposite(row, "free_throws_made", "free_throws_attempted")}</StatCell>
                    <StatCell>{atomicValue(row, "total_rebounds")}</StatCell>
                    <StatCell>{atomicValue(row, "assists")}</StatCell>
                    <StatCell>{atomicValue(row, "turnovers")}</StatCell>
                    <StatCell>{atomicValue(row, "blocks")}</StatCell>
                    <StatCell>{atomicValue(row, "steals")}</StatCell>
                    <StatCell strong>{atomicValue(row, "points")}</StatCell>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex flex-col gap-1 border-t border-gray-200 bg-gray-50 px-5 py-3 text-xs text-gray-500 sm:flex-row sm:items-center sm:justify-between sm:px-6">
            <span>Values retain the Sidearm source field and source snapshot for audit.</span>
            <span className="font-medium text-gray-700">
              {isLatestSnapshot ? "Verified against latest snapshot" : "Snapshot provenance retained"}
            </span>
          </div>
        </>
      )}
    </section>
  );
}

function StatHeading({ children, strong = false }: { children: React.ReactNode; strong?: boolean }) {
  return (
    <th scope="col" className={`px-2 py-2.5 text-right ${strong ? "text-gray-950" : ""}`}>
      {children}
    </th>
  );
}

function StatCell({ children, strong = false }: { children: React.ReactNode; strong?: boolean }) {
  return (
    <td className={`px-2 py-2.5 text-right font-mono tabular-nums ${strong ? "font-semibold text-gray-950" : "text-gray-700"}`}>
      {children}
    </td>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-6 rounded-lg border border-gray-200 bg-white p-5 sm:p-6">
      <h2 className="mb-4 text-lg font-semibold text-gray-950">{title}</h2>
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
    <section className="rounded-lg border border-gray-200 bg-white p-5">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.1em] text-yellow-700">
          Editorial tool
        </p>
        <h2 className="mt-1 text-lg font-semibold text-gray-950">AI coverage draft</h2>
        <p className="mt-1 text-xs leading-5 text-gray-500">
          Treat generated copy as a draft. Verify every publishable claim against the normalized facts.
        </p>
      </div>
      <button
        type="button"
        onClick={onGenerate}
        disabled={generating}
        className="mt-4 w-full rounded-md bg-gray-950 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-gray-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {generating ? "Generating..." : content ? "Regenerate draft" : "Generate coverage draft"}
      </button>

      {error && (
        <p role="alert" className="mt-4 border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
          {error}
        </p>
      )}

      {!content && !generating && !error && (
        <p className="mt-4 text-sm leading-5 text-gray-500">
          No draft yet. Generate a headline, recap, player spotlight, and social post from this boxscore.
        </p>
      )}

      {content && (
        <div className="mt-5 space-y-5 border-t border-gray-200 pt-5">
          {content.headline && (
            <div>
              <Label>Headline</Label>
              <p className="text-lg font-bold leading-snug text-gray-950">{content.headline}</p>
            </div>
          )}

          <CopyableBlock label="Recap" text={content.recap}>
            {content.recap.split(/\n\n+/).map((paragraph, index) => (
              <p key={index} className="mb-3 text-sm leading-6 text-gray-800 last:mb-0">
                {paragraph}
              </p>
            ))}
          </CopyableBlock>

          <CopyableBlock
            label={`Player spotlight${content.spotlight_player ? `: ${content.spotlight_player}` : ""}`}
            text={content.spotlight_body}
          >
            <p className="text-sm leading-6 text-gray-800">{content.spotlight_body}</p>
          </CopyableBlock>

          <CopyableBlock label="Social post" text={content.social_post}>
            <p className="border border-gray-200 bg-gray-50 p-3 font-mono text-xs leading-5 text-gray-800">
              {content.social_post}
            </p>
            <p className="mt-1 text-xs text-gray-400">{content.social_post.length} characters</p>
          </CopyableBlock>

          <p className="border-t border-gray-100 pt-3 text-xs leading-5 text-gray-400">
            Generated {new Date(content.generated_at).toLocaleString()}
            {content.model && ` / ${content.model}`}
            {history.length > 0 && ` / ${history.length} earlier version${history.length === 1 ? "" : "s"}`}
          </p>
        </div>
      )}
    </section>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">{children}</p>;
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
      <div className="mb-1 flex items-baseline justify-between gap-3">
        <Label>{label}</Label>
        <button
          type="button"
          onClick={copy}
          className="text-xs font-medium text-gray-500 underline decoration-gray-300 underline-offset-2 hover:text-gray-950 focus-visible:rounded-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500"
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
    <div className="overflow-x-auto" tabIndex={0}>
      <h3 className="mb-2 text-sm font-semibold text-gray-700">
        {categoryLabel(group.category)}
      </h3>
      <table className="w-full min-w-[40rem] text-sm">
        <thead>
          <tr className="border-b border-gray-200 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
            {group.columns.map((column, index) => (
              <th
                scope="col"
                key={column}
                className={index === 0 ? "py-2 pr-3" : "py-2 pr-3 text-right"}
              >
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {group.rows.map((row, index) => (
            <tr key={index} className="border-b border-gray-100 last:border-0">
              {row.map((cell, cellIndex) => (
                <td
                  key={`${cellIndex}-${cell}`}
                  className={
                    cellIndex === 0
                      ? "py-1.5 pr-3 text-gray-950"
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
