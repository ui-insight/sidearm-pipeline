import { api } from "./client";
import type { ArticleBrief, ArticleBriefCreate } from "../types/article";

export const articlesApi = {
  create: (payload: ArticleBriefCreate) =>
    api.post<ArticleBrief>("/articles", payload),
  get: (articleId: number) => api.get<ArticleBrief>(`/articles/${articleId}`),
};
