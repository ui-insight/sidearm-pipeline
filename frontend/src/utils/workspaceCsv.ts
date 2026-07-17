import type { Leaderboard } from "../types/recordBook";
import type {
  PlayerGameSplit,
  PlayerGameSplitGame,
  TeamSeasonRecord,
} from "../types/semanticQuery";

export interface ComparisonGameRow {
  game_id: number;
  game_date: string | null;
  season: string;
  opponent: string;
  venue: string | null;
  conference_event: boolean;
  left_value: string | null;
  left_source_url: string | null;
  right_value: string | null;
  right_source_url: string | null;
}

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

export function alignComparisonGames(
  left: PlayerGameSplit,
  right: PlayerGameSplit,
): ComparisonGameRow[] {
  const rows = new Map<number, ComparisonGameRow>();

  function addGame(game: PlayerGameSplitGame, side: "left" | "right") {
    const row = rows.get(game.game_id) ?? {
      game_id: game.game_id,
      game_date: game.game_date,
      season: game.season,
      opponent: game.opponent,
      venue: game.venue,
      conference_event: game.conference_event,
      left_value: null,
      left_source_url: null,
      right_value: null,
      right_source_url: null,
    };
    row[`${side}_value`] = game.value;
    row[`${side}_source_url`] = game.source_url;
    rows.set(game.game_id, row);
  }

  left.games.forEach((game) => addGame(game, "left"));
  right.games.forEach((game) => addGame(game, "right"));

  return Array.from(rows.values()).sort((first, second) => {
    const dateOrder = (first.game_date ?? "").localeCompare(
      second.game_date ?? "",
    );
    return dateOrder || first.game_id - second.game_id;
  });
}

export function buildPlayerComparisonCsv(
  left: PlayerGameSplit,
  right: PlayerGameSplit,
): string {
  const rows = [
    csvRow(["Vandals player comparison"]),
    csvRow(["Program", left.program_name]),
    csvRow(["Season", left.season]),
    csvRow(["Statistic", left.stat_label]),
    csvRow(["Conference scope", left.conference_scope]),
    csvRow(["Venue scope", left.venue_scope]),
    "",
    csvRow(["Player", "Value", "Games reviewed", "Open quality issues"]),
    csvRow([
      left.player_name,
      left.value,
      left.games_count,
      left.open_quality_issue_count,
    ]),
    csvRow([
      right.player_name,
      right.value,
      right.games_count,
      right.open_quality_issue_count,
    ]),
    "",
    csvRow([
      "Date",
      "Opponent",
      "Venue",
      "Conference",
      left.player_name,
      right.player_name,
      `${left.player_name} source`,
      `${right.player_name} source`,
    ]),
    ...alignComparisonGames(left, right).map((game) =>
      csvRow([
        game.game_date,
        game.opponent,
        game.venue,
        game.conference_event ? "Yes" : "No",
        game.left_value,
        game.right_value,
        game.left_source_url,
        game.right_source_url,
      ]),
    ),
  ];

  return `${rows.join("\n")}\n`;
}
