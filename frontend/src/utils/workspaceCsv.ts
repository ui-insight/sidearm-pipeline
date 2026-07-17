import type { Leaderboard } from "../types/recordBook";
import type { TeamSeasonRecord } from "../types/semanticQuery";

function csvCell(value: string | number | null | undefined): string {
  const text = value === null || value === undefined ? "" : String(value);
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function csvRow(values: (string | number | null | undefined)[]): string {
  return values.map(csvCell).join(",");
}

export function buildWorkspaceCsv(
  record: TeamSeasonRecord,
  leaderboard: Leaderboard,
): string {
  const rows = [
    csvRow(["Vandals season desk"]),
    csvRow(["Program", record.program_name]),
    csvRow(["Season", record.season]),
    csvRow(["Record scope", record.conference_scope]),
    csvRow(["Record", `${record.wins}-${record.losses}-${record.ties}`]),
    csvRow(["Leader statistic", leaderboard.stat_label]),
    "",
    csvRow([
      "Games",
      "Date",
      "Opponent",
      "Venue",
      "Conference",
      "Result",
      "Idaho score",
      "Opponent score",
      "Source",
    ]),
    ...record.games.map((game) =>
      csvRow([
        "Game",
        game.game_date,
        game.opponent,
        game.venue,
        game.conference_event ? "Yes" : "No",
        game.result,
        game.idaho_score,
        game.opponent_score,
        game.source_url,
      ]),
    ),
    "",
    csvRow(["Leaders", "Rank", "Player", leaderboard.stat_label, "Source"]),
    ...leaderboard.leaders.map((leader) =>
      csvRow([
        "Leader",
        leader.rank,
        leader.player_name,
        leader.total,
        leader.season_breakdown[0]?.source_url,
      ]),
    ),
  ];

  return `${rows.join("\n")}\n`;
}
