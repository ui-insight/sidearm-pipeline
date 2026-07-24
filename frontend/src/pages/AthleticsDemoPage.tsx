import { useEffect, useMemo, useState } from "react";
import { ApiError } from "../api/client";
import { pregameBriefsApi } from "../api/pregameBriefs";
import type {
  BriefGame,
  HistoricalPregameBrief,
} from "../types/pregameBrief";

const DEMO_SEASON = "2025-26";
const DEMO_OPPONENT = "Montana State";
const DEMO_GAME_DATE = "2026-02-05";

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "The historical briefing could not be loaded.";
}

function readableDate(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${value}T00:00:00Z`));
}

function scoreline(game: BriefGame): string {
  return `${game.result === "win" ? "W" : game.result === "loss" ? "L" : "T"} ${game.idaho_score}–${game.opponent_score}`;
}

function venueLabel(venue: string): string {
  if (venue === "home") return "Home";
  if (venue === "away") return "Away";
  if (venue === "neutral") return "Neutral";
  return "Venue unavailable";
}

function AthleticsDemoPage() {
  const [brief, setBrief] = useState<HistoricalPregameBrief | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [resultRevealed, setResultRevealed] = useState(false);

  useEffect(() => {
    let active = true;
    async function loadBrief() {
      try {
        const response = await pregameBriefsApi.historical(
          DEMO_SEASON,
          DEMO_OPPONENT,
          DEMO_GAME_DATE,
        );
        if (active) setBrief(response);
      } catch (loadError) {
        if (active) setError(errorMessage(loadError));
      } finally {
        if (active) setLoading(false);
      }
    }
    void loadBrief();
    return () => {
      active = false;
    };
  }, []);

  const recentRecord = useMemo(() => {
    const wins = brief?.recent_form.filter((game) => game.result === "win").length ?? 0;
    const losses = brief?.recent_form.filter((game) => game.result === "loss").length ?? 0;
    return `${wins}–${losses}`;
  }, [brief]);

  if (loading) {
    return (
      <div className="mx-auto max-w-6xl animate-pulse px-4 py-10 sm:px-6 lg:px-8" role="status">
        <div className="h-4 w-40 rounded bg-gray-200" />
        <div className="mt-4 h-10 w-80 max-w-full rounded bg-gray-200" />
        <div className="mt-10 grid gap-6 border-y border-gray-200 py-8 sm:grid-cols-3">
          <div className="h-24 rounded bg-gray-100" />
          <div className="h-24 rounded bg-gray-100" />
          <div className="h-24 rounded bg-gray-100" />
        </div>
        <span className="sr-only">Building historical pregame brief</span>
      </div>
    );
  }

  if (error || !brief) {
    return (
      <section className="mx-auto max-w-4xl px-4 py-10 sm:px-6" role="alert">
        <p className="text-xs font-black uppercase tracking-[0.12em] text-red-700">
          Brief unavailable
        </p>
        <h1 className="mt-2 text-2xl font-black text-gray-950">
          Historical evidence could not be assembled
        </h1>
        <p className="mt-3 text-sm text-gray-700">{error}</p>
      </section>
    );
  }

  const priorMeeting = brief.prior_meetings[0];
  const scoringLeader = brief.scoring_leaders[0];
  const target = brief.target_game;

  return (
    <article className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
      <header className="border-b-2 border-gray-950 pb-7">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs font-black uppercase tracking-[0.14em] text-amber-700">
            Historical pregame brief
          </p>
          <span className="rounded-full bg-gray-100 px-3 py-1 text-xs font-bold text-gray-700">
            No hindsight: data through {readableDate(brief.as_of_date)}
          </span>
        </div>
        <h1 className="mt-4 text-3xl font-black tracking-tight text-gray-950 sm:text-4xl">
          {target.opponent} at Idaho
        </h1>
        <p className="mt-2 text-base font-semibold text-gray-700">
          {readableDate(target.game_date)} · {venueLabel(target.venue)} · Women&apos;s basketball
        </p>
        <p className="mt-4 max-w-3xl text-sm leading-6 text-gray-600">
          A replay of what the sports desk could have known before tipoff, assembled from verified game evidence already in the warehouse.
        </p>
      </header>

      <section aria-labelledby="desk-knew" className="border-b border-gray-300 py-8">
        <p className="text-xs font-bold uppercase tracking-[0.08em] text-gray-500">
          Briefing snapshot
        </p>
        <h2 id="desk-knew" className="mt-2 text-2xl font-black text-gray-950">
          What the desk knew
        </h2>
        <dl className="mt-6 grid border-y border-gray-300 sm:grid-cols-3 sm:divide-x sm:divide-gray-300">
          <div className="py-5 sm:pr-6">
            <dt className="text-xs font-bold uppercase tracking-[0.08em] text-gray-500">Season position</dt>
            <dd className="mt-2 text-2xl font-black tabular-nums text-gray-950">
              {brief.season_record.wins}–{brief.season_record.losses}
            </dd>
            <dd className="mt-1 text-sm text-gray-600">
              Through {brief.season_record.games_played} final games
            </dd>
          </div>
          <div className="border-t border-gray-300 py-5 sm:border-t-0 sm:px-6">
            <dt className="text-xs font-bold uppercase tracking-[0.08em] text-gray-500">Recent form</dt>
            <dd className="mt-2 text-2xl font-black tabular-nums text-gray-950">{recentRecord}</dd>
            <dd className="mt-1 text-sm text-gray-600">Across the previous five games</dd>
          </div>
          <div className="border-t border-gray-300 py-5 sm:border-t-0 sm:pl-6">
            <dt className="text-xs font-bold uppercase tracking-[0.08em] text-gray-500">Scoring lead</dt>
            <dd className="mt-2 text-lg font-black text-gray-950">
              {scoringLeader?.player_name ?? "Not available"}
            </dd>
            <dd className="mt-1 text-sm tabular-nums text-gray-600">
              {scoringLeader ? `${scoringLeader.points_per_game} points per game` : "No scoring evidence"}
            </dd>
          </div>
        </dl>
      </section>

      <section className="grid border-b border-gray-300 py-8 lg:grid-cols-[15rem_1fr] lg:gap-10">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.08em] text-gray-500">Editorial angle</p>
          <h2 className="mt-2 text-xl font-black text-gray-950">The rematch question</h2>
        </div>
        <div className="mt-5 lg:mt-0">
          {priorMeeting ? (
            <>
              <p className="max-w-3xl text-lg font-semibold leading-8 text-gray-900">
                Idaho entered on a {recentRecord} run after losing {priorMeeting.idaho_score}–{priorMeeting.opponent_score} at Montana State in the first meeting.
              </p>
              <a
                href={priorMeeting.source_url}
                target="_blank"
                rel="noreferrer"
                className="mt-3 inline-block text-sm font-bold text-gray-700 underline decoration-amber-500 underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-yellow-500"
              >
                Verify the first meeting box score
              </a>
            </>
          ) : (
            <p className="text-sm text-gray-600">No earlier meeting was available before the cutoff.</p>
          )}
        </div>
      </section>

      <section aria-labelledby="form-heading" className="border-b border-gray-300 py-8">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.08em] text-gray-500">Source ledger</p>
            <h2 id="form-heading" className="mt-2 text-xl font-black text-gray-950">Previous five games</h2>
          </div>
          <p className="text-xs text-gray-500">Each row opens the authoritative box score</p>
        </div>
        <div className="mt-5 overflow-x-auto border-y border-gray-300">
          <table className="w-full min-w-[38rem] text-left text-sm">
            <thead className="bg-gray-100 text-xs uppercase tracking-[0.06em] text-gray-600">
              <tr>
                <th className="px-3 py-3 font-bold">Date</th>
                <th className="px-3 py-3 font-bold">Opponent</th>
                <th className="px-3 py-3 font-bold">Site</th>
                <th className="px-3 py-3 text-right font-bold">Result</th>
                <th className="px-3 py-3 text-right font-bold">Evidence</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {brief.recent_form.map((game) => (
                <tr key={game.game_id}>
                  <td className="whitespace-nowrap px-3 py-3 text-gray-600">{readableDate(game.game_date)}</td>
                  <td className="px-3 py-3 font-semibold text-gray-950">{game.opponent}</td>
                  <td className="px-3 py-3 text-gray-600">{venueLabel(game.venue)}</td>
                  <td className="px-3 py-3 text-right font-mono font-bold text-gray-950">{scoreline(game)}</td>
                  <td className="px-3 py-3 text-right">
                    <a className="font-bold text-gray-700 underline decoration-amber-500 underline-offset-4" href={game.source_url} target="_blank" rel="noreferrer">Box score</a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="leaders-heading" className="border-b border-gray-300 py-8">
        <p className="text-xs font-bold uppercase tracking-[0.08em] text-gray-500">Player preparation</p>
        <h2 id="leaders-heading" className="mt-2 text-xl font-black text-gray-950">Scoring leaders at the cutoff</h2>
        <ol className="mt-5 divide-y divide-gray-200 border-y border-gray-300">
          {brief.scoring_leaders.map((leader, index) => (
            <li key={leader.player_id} className="grid gap-2 py-4 sm:grid-cols-[2rem_1fr_auto_auto] sm:items-center sm:gap-6">
              <span className="font-mono text-sm font-black text-amber-700">{String(index + 1).padStart(2, "0")}</span>
              <span className="font-bold text-gray-950">{leader.player_name}</span>
              <span className="text-sm tabular-nums text-gray-600">{leader.total_points} points · {leader.games_played} games</span>
              <span className="text-right font-mono font-black tabular-nums text-gray-950">{leader.points_per_game} PPG</span>
            </li>
          ))}
        </ol>
      </section>

      <section className="py-8">
        <div className="border border-gray-300 bg-white px-5 py-6 sm:flex sm:items-center sm:justify-between sm:gap-8">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.08em] text-gray-500">After the briefing</p>
            <h2 className="mt-2 text-xl font-black text-gray-950">Reveal what happened</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-gray-600">
              The result stays separate from every pregame calculation, making the historical replay auditable.
            </p>
          </div>
          <button
            type="button"
            aria-expanded={resultRevealed}
            onClick={() => setResultRevealed((current) => !current)}
            className="mt-5 shrink-0 rounded-md bg-gray-950 px-4 py-2 text-sm font-bold text-white transition-colors hover:bg-gray-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-yellow-500 sm:mt-0"
          >
            {resultRevealed ? "Hide result" : "Reveal result"}
          </button>
        </div>
        {resultRevealed ? (
          <div className="border-x border-b border-gray-300 bg-amber-50 px-5 py-5" role="status">
            <p className="text-xs font-black uppercase tracking-[0.08em] text-amber-800">Actual result</p>
            <p className="mt-2 text-2xl font-black tabular-nums text-gray-950">
              Idaho {target.idaho_score}, {target.opponent} {target.opponent_score}
            </p>
            <p className="mt-2 text-sm text-gray-700">The Vandals answered the rematch question with a three-point home win.</p>
            <a className="mt-3 inline-block text-sm font-bold text-gray-800 underline decoration-amber-500 underline-offset-4" href={target.source_url} target="_blank" rel="noreferrer">Open the final box score</a>
          </div>
        ) : null}
        <p className="mt-5 max-w-3xl text-xs leading-5 text-gray-500">
          Method: {brief.methodology} {brief.evidence_game_count} eligible games were checked.
        </p>
      </section>
    </article>
  );
}

export default AthleticsDemoPage;
