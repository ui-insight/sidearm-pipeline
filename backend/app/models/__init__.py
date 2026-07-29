"""SQLAlchemy ORM models.

Add one file per resource (e.g., user.py, project.py).
Import all models here so they are registered with Base.metadata.
"""

from app.models.achievement import (
    AchievementSuggestion,
    NotabilityPolicy,
    NotabilityPolicyMetric,
)
from app.models.article import (
    Article,
    ArticleAchievementSuggestion,
    ArticleEvidenceRevalidation,
    ArticleGenerationJob,
    ArticleReadinessDecision,
    ArticleVersion,
    ArticleWarningOverride,
    EvidenceBundle,
    StyleGuideVersion,
)
from app.models.content import GeneratedContent
from app.models.coverage_window import CoverageWindow
from app.models.data_quality_issue import DataQualityIssue
from app.models.game import (
    EventSource,
    EventStatusHistory,
    Game,
    IngestRun,
    PlayerStatGroup,
    ScoringPlay,
    SourceSnapshot,
    TeamStat,
)
from app.models.player import Player, PlayerExternalIdentity, PlayerSeason
from app.models.player_game_stat import PlayerGameStat
from app.models.player_identity_resolution import PlayerIdentityResolution
from app.models.player_season_stat import PlayerSeasonStat
from app.models.sport_program import SportProgram
from app.models.stat_definition import StatDefinition
from app.models.team import OpponentAlias, Team
from app.models.team_game_stat import TeamGameStat
from app.models.team_season_stat import TeamSeasonStat
from app.models.workspace_view import WorkspaceView

__all__ = [
    "AchievementSuggestion",
    "Article",
    "ArticleAchievementSuggestion",
    "ArticleEvidenceRevalidation",
    "ArticleGenerationJob",
    "ArticleReadinessDecision",
    "ArticleVersion",
    "ArticleWarningOverride",
    "CoverageWindow",
    "DataQualityIssue",
    "EventSource",
    "EventStatusHistory",
    "EvidenceBundle",
    "Game",
    "GeneratedContent",
    "IngestRun",
    "NotabilityPolicy",
    "NotabilityPolicyMetric",
    "OpponentAlias",
    "Player",
    "PlayerExternalIdentity",
    "PlayerGameStat",
    "PlayerIdentityResolution",
    "PlayerSeason",
    "PlayerSeasonStat",
    "PlayerStatGroup",
    "ScoringPlay",
    "SourceSnapshot",
    "SportProgram",
    "StatDefinition",
    "StyleGuideVersion",
    "Team",
    "TeamGameStat",
    "TeamSeasonStat",
    "TeamStat",
    "WorkspaceView",
]
