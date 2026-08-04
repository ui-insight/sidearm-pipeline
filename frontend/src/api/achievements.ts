import { api } from "./client";
import type {
  AchievementReviewQueue,
  AchievementReviewState,
  AchievementSuggestion,
} from "../types/achievement";

export const achievementsApi = {
  forGame: (gameId: number) =>
    api.get<AchievementSuggestion[]>(`/achievement-suggestions/games/${gameId}`),
  reviewQueue: (state: AchievementReviewState, limit = 25, offset = 0) =>
    api.get<AchievementReviewQueue>("/achievement-suggestions/review-queue", {
      state,
      limit: String(limit),
      offset: String(offset),
    }),
  verdict: (suggestionId: number, state: "approved" | "rejected") =>
    api.patch<AchievementSuggestion>(
      `/achievement-suggestions/${suggestionId}/verdict`,
      { state },
    ),
};
