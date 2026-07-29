import { api } from "./client";
import type {
  ArticleBrief,
  ArticleBriefCreate,
  ArticleGenerationJob,
  ArticleQueue,
  ArticleReadyResult,
  ArticleVersion,
  ArticleVersionCreate,
} from "../types/article";

export const articlesApi = {
  list: () => api.get<ArticleQueue>("/articles"),
  create: (payload: ArticleBriefCreate) =>
    api.post<ArticleBrief>("/articles", payload),
  get: (articleId: number) => api.get<ArticleBrief>(`/articles/${articleId}`),
  refreshEvidence: (articleId: number) =>
    api.post<ArticleBrief>(`/articles/${articleId}/revalidation/refresh`),
  generateDraft: (
    articleId: number,
    idempotencyKey: string,
    revision?: { baseVersionId: number; editorInstructions: string },
  ) =>
    api.post<ArticleGenerationJob>(`/articles/${articleId}/generation-jobs`, {
      idempotency_key: idempotencyKey,
      base_version_id: revision?.baseVersionId ?? null,
      editor_instructions: revision?.editorInstructions ?? null,
    }),
  getGenerationJob: (articleId: number, jobId: number) =>
    api.get<ArticleGenerationJob>(
      `/articles/${articleId}/generation-jobs/${jobId}`,
    ),
  saveVersion: (articleId: number, payload: ArticleVersionCreate) =>
    api.post<ArticleVersion>(`/articles/${articleId}/versions`, payload),
  markReady: (
    articleId: number,
    versionId: number,
    warningOverrides: Array<{ finding_code: string; reason: string }>,
  ) =>
    api.post<ArticleReadyResult>(
      `/articles/${articleId}/versions/${versionId}/ready`,
      { warning_overrides: warningOverrides },
    ),
};
