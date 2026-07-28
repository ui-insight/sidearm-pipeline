import { api } from "./client";
import type {
  ArticleBrief,
  ArticleBriefCreate,
  ArticleGenerationJob,
} from "../types/article";

export const articlesApi = {
  create: (payload: ArticleBriefCreate) =>
    api.post<ArticleBrief>("/articles", payload),
  get: (articleId: number) => api.get<ArticleBrief>(`/articles/${articleId}`),
  generateDraft: (articleId: number, idempotencyKey: string) =>
    api.post<ArticleGenerationJob>(`/articles/${articleId}/generation-jobs`, {
      idempotency_key: idempotencyKey,
    }),
  getGenerationJob: (articleId: number, jobId: number) =>
    api.get<ArticleGenerationJob>(
      `/articles/${articleId}/generation-jobs/${jobId}`,
    ),
};
