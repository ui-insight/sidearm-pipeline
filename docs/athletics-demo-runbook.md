# Athletics Demo Runbook

This runbook prepares a ten-minute internal demonstration of the women's
basketball warehouse and Exploratory Workspace. Use the completed 2025-26 season
unless Athletics selects another verified Coverage Window.

## Demo claim

An athletics staff member can answer a governed season, opponent, or player
question without SQL, inspect the evidence behind every result, and share or
export the view.

## Preparation

1. Start the PostgreSQL-backed application and sign in with the shared prototype
   credential configured for the demo environment.
2. From **Games**, run **Sync current WBB season** for 2025-26.
3. Confirm the sync reports no failed boxscores.
4. Resolve every actionable item in **Identity queue**. Do not guess when the
   source evidence is ambiguous.
5. Import or reconcile cumulative season statistics if the season leaderboard is
   unavailable.
6. Open **Demo** and clear every readiness gate. A warning is a stop signal, not
   presentation decoration.
7. Open each generated walkthrough once before the meeting and confirm its
   source links resolve.

## Ten-minute walkthrough

### 1. Season desk

Ask: "What was Idaho's record, and who led the selected statistic in 2025-26?"

- Open the generated season view from **Demo**.
- Point out that the record and leaderboard are warehouse-computed.
- Show the Coverage Window and open-quality-issue statement.
- Open one source link, then return to the workspace.

### 2. Opponent view

Ask: "What happened against this opponent, and which players contributed?"

- Open the generated opponent view.
- Show that the record, leaderboard, and game ledger use the same filters.
- Open a contributing boxscore as evidence.
- Export the current view to CSV.

### 3. Player comparison

Ask: "How did these two players compare over the same verified games?"

- Open the generated comparison.
- Show the shared season, metric, venue, conference, and opponent filters.
- Explain that the totals come from governed queries, not browser arithmetic.
- Copy the shareable URL or save the view.

## Stop conditions

Do not present the result as authoritative when any of these conditions apply:

- failed final-boxscore ingestion
- unresolved player identity affecting the selected question
- an open error or critical data-quality issue in scope
- missing source links
- unavailable or partial Coverage Window presented as complete history

## Environment checklist

- `DEV_MODE=false`
- `PROTOTYPE_AUTH_ENABLED=true`
- non-default `SECRET_KEY`
- strong demo-only prototype password shared through an approved channel
- HTTPS and a restricted CORS origin
- PostgreSQL backup taken before the demonstration
- a tested fallback recording or screenshots in case Sidearm is unavailable

The prototype credential is suitable only for a limited internal demonstration.
Per-person authentication and RBAC remain a staff-pilot gate.
