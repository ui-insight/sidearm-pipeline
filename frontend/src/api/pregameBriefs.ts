import { api } from "./client";
import type { HistoricalPregameBrief } from "../types/pregameBrief";

export const pregameBriefsApi = {
  historical: (season: string, opponent: string, gameDate: string) =>
    api.get<HistoricalPregameBrief>("/pregame-briefs/historical", {
      season,
      opponent,
      game_date: gameDate,
    }),
};
