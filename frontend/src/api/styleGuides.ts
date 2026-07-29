import { api } from "./client";
import type {
  ResolvedStyleGuide,
  StyleGuideContentRequest,
  StyleGuideCreateRequest,
  StyleGuidePreviewRequest,
  StyleGuideVersion,
} from "../types/styleGuide";

export const styleGuidesApi = {
  list: () => api.get<StyleGuideVersion[]>("/style-guides"),
  create: (request: StyleGuideCreateRequest) =>
    api.post<StyleGuideVersion>("/style-guides", request),
  createSuccessor: (versionId: number, request: StyleGuideContentRequest) =>
    api.post<StyleGuideVersion>(
      `/style-guides/${versionId}/successors`,
      request,
    ),
  preview: (request: StyleGuidePreviewRequest) =>
    api.post<ResolvedStyleGuide>("/style-guides/preview", request),
  activate: (versionId: number) =>
    api.post<StyleGuideVersion>(`/style-guides/${versionId}/activate`, {}),
  retire: (versionId: number) =>
    api.post<StyleGuideVersion>(`/style-guides/${versionId}/retire`, {}),
};
