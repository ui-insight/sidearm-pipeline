"""Evidence-backed historical pregame briefing schemas."""

from decimal import Decimal

from pydantic import BaseModel


class BriefGameRead(BaseModel):
    """One game used as evidence in a historical briefing."""

    game_id: int
    game_date: str
    opponent: str
    venue: str
    idaho_score: int
    opponent_score: int
    result: str
    source_url: str


class BriefRecordRead(BaseModel):
    """Idaho's record through the briefing cutoff."""

    games_played: int
    wins: int
    losses: int
    ties: int


class BriefPlayerLeaderRead(BaseModel):
    """One scoring leader using only games before the target matchup."""

    player_id: int
    player_name: str
    games_played: int
    total_points: Decimal
    points_per_game: Decimal
    evidence: list[BriefGameRead]


class BriefTargetGameRead(BaseModel):
    """The selected historical matchup, including its concealed result."""

    game_id: int
    game_date: str
    opponent: str
    venue: str
    source_url: str
    idaho_score: int
    opponent_score: int
    result: str


class PregameBriefRead(BaseModel):
    """A deterministic pregame brief constrained to a historical cutoff."""

    program_name: str
    season: str
    as_of_date: str
    target_game: BriefTargetGameRead
    season_record: BriefRecordRead
    recent_form: list[BriefGameRead]
    prior_meetings: list[BriefGameRead]
    scoring_leaders: list[BriefPlayerLeaderRead]
    evidence_game_count: int
    methodology: str
