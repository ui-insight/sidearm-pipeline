"""SQLAlchemy ORM models.

Add one file per resource (e.g., user.py, project.py).
Import all models here so they are registered with Base.metadata.
"""

from app.models.agent import AgentRun, AgentRunEvaluation, AgentRunStep
from app.models.content import GeneratedContent
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

__all__ = [
    "AgentRun",
    "AgentRunEvaluation",
    "AgentRunStep",
    "EventSource",
    "EventStatusHistory",
    "Game",
    "GeneratedContent",
    "IngestRun",
    "PlayerStatGroup",
    "ScoringPlay",
    "SourceSnapshot",
    "TeamStat",
]
