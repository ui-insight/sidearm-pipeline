export type StyleGuideScope =
  | "shared_athletics"
  | "sport"
  | "article_type"
  | "channel";

export type StyleGuideState = "draft" | "active" | "retired";
export type StyleGuideSeverity = "error" | "warning" | "guidance";
export type StyleGuideEnforcement =
  | "prompt_guidance"
  | "deterministic_lint"
  | "required_terms"
  | "forbidden_terms"
  | "headline_max_chars"
  | "body_max_chars"
  | "forbidden_fact_classes";

export interface StyleGuideRule {
  key: string;
  category: string;
  severity: StyleGuideSeverity;
  enforcement: StyleGuideEnforcement;
  value: string | number | string[];
  override: boolean;
  description: string | null;
}

export interface StyleGuideVersion {
  id: number;
  guide_key: string;
  version: number;
  predecessor_version_id: number | null;
  name: string;
  scope_type: StyleGuideScope;
  scope_value: string | null;
  instructions: string;
  rules: StyleGuideRule[];
  content_hash: string;
  lifecycle_state: StyleGuideState;
  created_by: string;
  created_at: string;
  effective_at: string | null;
  activated_at: string | null;
  activated_by: string | null;
  retired_at: string | null;
  retired_by: string | null;
}

export interface StyleGuideContentRequest {
  name: string;
  instructions: string;
  rules: StyleGuideRule[];
}

export interface StyleGuideCreateRequest extends StyleGuideContentRequest {
  guide_key: string;
  scope_type: StyleGuideScope;
  scope_value: string | null;
}

export interface StyleGuidePreviewRequest {
  sport: string | null;
  article_type: "game_recap" | "player_spotlight" | "achievement_story";
  channel: string | null;
  candidate_version_id: number | null;
}

export interface ResolvedStyleGuideRule extends StyleGuideRule {
  source_version_id: number;
  source_guide_key: string;
  source_scope_type: StyleGuideScope;
  source_scope_value: string | null;
}

export interface ResolvedStyleGuide {
  sport: string | null;
  article_type: "game_recap" | "player_spotlight" | "achievement_story";
  channel: string | null;
  versions: Array<{
    id: number;
    guide_key: string;
    version: number;
    name: string;
    scope_type: StyleGuideScope;
    scope_value: string | null;
    content_hash: string;
  }>;
  instructions: string[];
  rules: ResolvedStyleGuideRule[];
  style_hash: string;
  valid_for_activation: boolean;
  issues: Array<{
    code: string;
    message: string;
    rule_key: string | null;
    version_ids: number[];
  }>;
}
