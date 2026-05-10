"""Sport-specific validation rules for game publication readiness."""

from dataclasses import dataclass, field

from app.models.game import Game

SPORTS_REQUIRING_SCORING_PLAYS = {"football", "mens-basketball", "womens-basketball"}


@dataclass
class ValidationCheck:
    """Result of a single validation rule."""

    rule: str
    passed: bool
    detail: str | None = field(default=None)


def validate_game(game: Game) -> list[ValidationCheck]:
    """Run all validation rules against a game. Returns ordered list of checks."""
    checks: list[ValidationCheck] = []

    # Always-required fields
    checks.append(
        ValidationCheck(
            rule="has_sport",
            passed=game.sport is not None,
            detail=None if game.sport is not None else "sport is null",
        )
    )
    checks.append(
        ValidationCheck(
            rule="has_season",
            passed=game.season is not None,
            detail=None if game.season is not None else "season is null",
        )
    )
    checks.append(
        ValidationCheck(
            rule="has_game_date",
            passed=game.game_date is not None,
            detail=None if game.game_date is not None else "game_date is null",
        )
    )
    has_teams = game.home_team is not None and game.away_team is not None
    checks.append(
        ValidationCheck(
            rule="has_teams",
            passed=has_teams,
            detail=None
            if has_teams
            else f"home_team={game.home_team!r} away_team={game.away_team!r}",
        )
    )
    checks.append(
        ValidationCheck(
            rule="has_title",
            passed=game.title is not None,
            detail=None if game.title is not None else "title is null",
        )
    )

    # Final-event checks
    is_final = game.event_status == "final"

    has_score = game.home_score is not None and game.away_score is not None
    if is_final:
        checks.append(
            ValidationCheck(
                rule="has_score",
                passed=has_score,
                detail=None
                if has_score
                else f"home_score={game.home_score!r} away_score={game.away_score!r}",
            )
        )
        if has_score:
            scores_non_negative = game.home_score >= 0 and game.away_score >= 0
            checks.append(
                ValidationCheck(
                    rule="score_non_negative",
                    passed=scores_non_negative,
                    detail=None
                    if scores_non_negative
                    else f"home_score={game.home_score} away_score={game.away_score}",
                )
            )

        has_team_stats = len(game.team_stats) > 0
        checks.append(
            ValidationCheck(
                rule="has_team_stats",
                passed=has_team_stats,
                detail=None if has_team_stats else "team_stats is empty",
            )
        )

        if game.sport in SPORTS_REQUIRING_SCORING_PLAYS:
            has_scoring_plays = len(game.scoring_plays) > 0
            checks.append(
                ValidationCheck(
                    rule="scoring_plays_present",
                    passed=has_scoring_plays,
                    detail=None if has_scoring_plays else "scoring_plays is empty",
                )
            )

    return checks


def all_passed(checks: list[ValidationCheck]) -> bool:
    """Return True if every check in the list passed."""
    return all(c.passed for c in checks)
