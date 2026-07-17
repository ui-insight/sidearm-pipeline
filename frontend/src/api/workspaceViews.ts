import { api } from "./client";
import type { WorkspaceViewKind } from "../utils/savedWorkspaceViews";

export interface SharedWorkspaceView {
  id: string;
  name: string;
  view: WorkspaceViewKind;
  params: Record<string, string>;
  created_by: string;
  created_at: string;
}

interface CreateSharedWorkspaceViewRequest {
  name: string;
  view: WorkspaceViewKind;
  params: Record<string, string>;
}

export function listSharedWorkspaceViews(): Promise<SharedWorkspaceView[]> {
  return api.get<SharedWorkspaceView[]>("/workspace-views");
}

export function createSharedWorkspaceView(
  request: CreateSharedWorkspaceViewRequest,
): Promise<SharedWorkspaceView> {
  return api.post<SharedWorkspaceView>("/workspace-views", request);
}

export function deleteSharedWorkspaceView(viewId: string): Promise<void> {
  return api.delete<void>(`/workspace-views/${viewId}`);
}
