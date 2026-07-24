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
    """One Vandal leader using only games before the target matchup."""

    player_id: int
    player_name: str
    team_name: str
    jersey_number: str | None = None
    position: str | None = None
    class_year: str | None = None
    bio_url: str | None = None
    games_played: int
    total: Decimal
    per_game: Decimal
    evidence: list[BriefGameRead]


class BriefLeaderGroupRead(BaseModel):
    """A relevant basketball metric and its leading Idaho players."""

    stat_key: str
    label: str
    context: str
    leaders: list[BriefPlayerLeaderRead]


class PreviousMatchupPlayerRead(BaseModel):
    """One standout line parsed from the retained first-meeting box score."""

    team_name: str
    player_name: str
    jersey_number: str | None = None
    starter: bool
    minutes: int
    points: int
    rebounds: int
    assists: int
    steals: int
    blocks: int


class PreviousMatchupTeamRead(BaseModel):
    """The most consequential player lines for one first-meeting team."""

    team_name: str
    standouts: list[PreviousMatchupPlayerRead]


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
    vandal_leader_groups: list[BriefLeaderGroupRead]
    previous_matchup_teams: list[PreviousMatchupTeamRead]
    evidence_game_count: int
    methodology: str
