import { expect, test } from "@playwright/test";

test("season desk assembles evidence and exports it", async ({ page }) => {
  await page.route("**/api/v1/auth/session", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ authenticated: true, username: "e2e-user" }),
    });
  });
  await page.route("**/api/v1/semantic-queries/options", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        program_slug: "womens-basketball",
        program_name: "Women's Basketball",
        seasons: ["2025-26"],
        metrics: [
          {
            stat_key: "points",
            display_label: "Points",
            value_type: "integer",
            unit: "count",
            aggregation_method: "sum",
            comparison_direction: "higher",
            display_format: "0",
          },
        ],
        players: [],
        opponents: [
          {
            opponent_name: "Washington State",
            seasons: ["2025-26"],
          },
        ],
        leader_limits: [5, 10],
        default_season: "2025-26",
        default_stat_key: "points",
      }),
    });
  });
  await page.route("**/api/v1/semantic-queries/execute", async (route) => {
    const body = route.request().postDataJSON() as {
      query_id: string;
      season: string;
      stat_key: string;
      conference_scope: string;
      opponent?: string;
    };
    if (body.query_id === "team_season_record") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          query_id: "team_season_record",
          result: {
            program_slug: "womens-basketball",
            program_name: "Women's Basketball",
            season: "2025-26",
            conference_scope: "all",
            opponent: body.opponent ?? null,
            games_played: 1,
            wins: 1,
            losses: 0,
            ties: 0,
            open_quality_issue_count: 0,
            coverage: {
              grain: "game",
              first_season: "2025-26",
              last_season: "2025-26",
              completeness: "complete",
              source_systems: ["sidearm"],
              known_limitations: [],
              verified_at: "2026-07-15T20:00:00Z",
              statement: "Verified source evidence covers the selected game.",
            },
            games: [
              {
                game_id: 21,
                game_date: "2025-11-06",
                opponent: "Washington State",
                venue: "home",
                conference_event: false,
                idaho_score: 72,
                opponent_score: 64,
                result: "win",
                source_url: "https://govandals.com/boxscore/21",
              },
            ],
          },
        }),
      });
      return;
    }

    if (body.query_id === "opponent_stat_leaders") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          query_id: "opponent_stat_leaders",
          result: {
            program_slug: "womens-basketball",
            program_name: "Women's Basketball",
            stat_key: body.stat_key,
            stat_label: "Points",
            aggregation_method: "sum",
            season: body.season,
            conference_scope: body.conference_scope,
            opponent: body.opponent,
            total_players: 1,
            open_quality_issue_count: 0,
            coverage: {
              grain: "game",
              first_season: "2025-26",
              last_season: "2025-26",
              completeness: "complete",
              source_systems: ["sidearm"],
              known_limitations: [],
              verified_at: "2026-07-15T20:00:00Z",
              statement: "Verified game-grain sources cover 2025-26.",
            },
            leaders: [
              {
                rank: 1,
                player_id: 4,
                player_name: "Alice Adams",
                total: "18",
                games_count: 1,
                games: [
                  {
                    game_id: 21,
                    game_date: "2025-11-06",
                    season: "2025-26",
                    opponent: "Washington State",
                    venue: "home",
                    conference_event: false,
                    value: "18",
                    source_snapshot_id: 21,
                    source_url: "https://govandals.com/boxscore/21",
                  },
                ],
              },
            ],
          },
        }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        query_id: "stat_leaders",
        result: {
          program_slug: "womens-basketball",
          program_name: "Women's Basketball",
          stat_key: "points",
          stat_label: "Points",
          scope: "season",
          season: "2025-26",
          available_seasons: ["2025-26"],
          total_players: 1,
          open_quality_issue_count: 0,
          coverage: {
            first_season: "2025-26",
            last_season: "2025-26",
            completeness: "complete",
            source_systems: ["sidearm"],
            known_limitations: [],
            verified_at: "2026-07-15T20:00:00Z",
            statement: "Verified player totals cover the selected season.",
          },
          leaders: [
            {
              rank: 1,
              player_id: 4,
              player_name: "Alice Adams",
              total: "225",
              seasons_count: 1,
              season_breakdown: [
                {
                  season: "2025-26",
                  value: "225",
                  source_snapshot_id: 12,
                  source_url: "https://govandals.com/stats/wbb/2025-26",
                },
              ],
            },
          ],
        },
      }),
    });
  });

  await page.goto("/workspace");

  await expect(
    page.getByRole("heading", { name: "Idaho finished 1–0 in 2025-26." }),
  ).toBeVisible();
  await expect(page.getByText("Alice Adams")).toBeVisible();
  await expect(
    page.getByRole("table").getByText("Washington State", { exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Workspace" })).toHaveAttribute(
    "aria-current",
    "page",
  );

  await page.getByLabel("Opponent").selectOption("Washington State");
  await expect(page).toHaveURL(/opponent=Washington\+State/);
  await expect(
    page.getByRole("heading", {
      name: "Idaho finished 1–0 in 2025-26 against Washington State.",
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", {
      name: "View game 1 source for Alice Adams against Washington State",
    }),
  ).toHaveAttribute("href", "https://govandals.com/boxscore/21");

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export CSV" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(
    "wbb-2025-26-points-all-washington-state.csv",
  );
});
