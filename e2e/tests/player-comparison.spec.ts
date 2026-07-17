import { expect, test } from "@playwright/test";

test("player comparison keeps shared filters, evidence, and export together", async ({
  context,
  page,
}) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
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
        players: [
          {
            player_id: 4,
            player_name: "Alice Adams",
            seasons: ["2025-26"],
          },
          {
            player_id: 8,
            player_name: "Bobbi Brown",
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
      player_id?: number;
      season: string;
      stat_key: string;
      conference_scope: string;
      venue_scope: string;
      limit?: number;
    };
    const coverage = {
      grain: "game",
      first_season: "2025-26",
      last_season: "2025-26",
      completeness: "complete",
      source_systems: ["sidearm"],
      known_limitations: [],
      verified_at: "2026-07-15T20:00:00Z",
      statement: "Verified game evidence covers the selected season.",
    };
    if (body.query_id === "team_season_record") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          query_id: body.query_id,
          result: {
            program_slug: "womens-basketball",
            program_name: "Women's Basketball",
            season: body.season,
            conference_scope: body.conference_scope,
            games_played: 1,
            wins: 1,
            losses: 0,
            ties: 0,
            open_quality_issue_count: 0,
            coverage,
            games: [
              {
                game_id: 21,
                game_date: "2026-01-03",
                opponent: "Montana",
                venue: "home",
                conference_event: true,
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
    if (body.query_id === "stat_leaders") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          query_id: body.query_id,
          result: {
            program_slug: "womens-basketball",
            program_name: "Women's Basketball",
            stat_key: body.stat_key,
            stat_label: "Points",
            scope: "season",
            season: body.season,
            available_seasons: ["2025-26"],
            total_players: 2,
            open_quality_issue_count: 0,
            coverage,
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
      return;
    }
    const isAlice = body.player_id === 4;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        query_id: "player_game_split",
        result: {
          program_slug: "womens-basketball",
          program_name: "Women's Basketball",
          player_id: body.player_id,
          player_name: isAlice ? "Alice Adams" : "Bobbi Brown",
          stat_key: body.stat_key,
          stat_label: "Points",
          aggregation_method: "sum",
          season: body.season,
          conference_scope: body.conference_scope,
          venue_scope: body.venue_scope,
          value: isAlice ? "20" : "12",
          games_count: 1,
          open_quality_issue_count: 0,
          coverage: {
            grain: "game",
            first_season: "2025-26",
            last_season: "2025-26",
            completeness: "complete",
            source_systems: ["sidearm"],
            known_limitations: [],
            verified_at: "2026-07-15T20:00:00Z",
            statement: "Verified game evidence covers the selected season.",
          },
          games: [
            {
              game_id: 21,
              game_date: "2026-01-03",
              season: "2025-26",
              opponent: "Montana",
              venue: "home",
              conference_event: true,
              value: isAlice ? "20" : "12",
              source_snapshot_id: 21,
              source_url: "https://govandals.com/boxscore/21",
            },
          ],
        },
      }),
    });
  });

  await page.goto(
    "/workspace/compare?season=2025-26&stat=points&conference=all&venue=all&left=4&right=8",
  );

  await expect(
    page.getByRole("heading", { name: "Alice Adams vs. Bobbi Brown" }),
  ).toBeVisible();
  await expect(
    page.getByRole("progressbar", { name: "Alice Adams: 20 Points" }),
  ).toBeVisible();
  await expect(page.getByText("Montana", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("link", {
      name: "View Bobbi Brown source against Montana",
    }),
  ).toHaveAttribute("href", "https://govandals.com/boxscore/21");
  await expect(
    page.getByRole("link", { name: "Player comparison" }),
  ).toHaveAttribute("aria-current", "page");

  await page.getByLabel("Venue").selectOption("home");
  await expect(page).toHaveURL(/venue=home/);
  await page.goBack();
  await expect(page).toHaveURL(/venue=all/);
  await expect(page.getByLabel("Venue")).toHaveValue("all");

  await page.getByRole("button", { name: "Share link" }).click();
  await expect(page.getByText("Share link copied.")).toBeVisible();
  await expect
    .poll(() => page.evaluate(() => navigator.clipboard.readText()))
    .toBe(page.url());

  await page.getByRole("button", { name: "Save view" }).click();
  await page.getByLabel("View name").fill("Deadline check");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByText("View saved in this browser.")).toBeVisible();

  await page.goto("/workspace");
  await expect(page.getByRole("heading", { name: "Season desk" })).toBeVisible();
  const savedViews = page.getByLabel("Saved in this browser");
  await savedViews.selectOption({ label: "Comparison: Deadline check" });
  await page.getByRole("button", { name: "Open" }).click();
  await expect(page).toHaveURL(
    /\/workspace\/compare\?season=2025-26&stat=points&conference=all&venue=all&left=4&right=8$/,
  );
  await expect(
    page.getByRole("heading", { name: "Alice Adams vs. Bobbi Brown" }),
  ).toBeVisible();
  await page.getByLabel("Saved in this browser").selectOption({
    label: "Comparison: Deadline check",
  });
  const deleteSavedView = page.getByRole("button", { name: "Delete" });
  await expect(deleteSavedView).toBeEnabled();
  await deleteSavedView.click();
  await expect(page.getByText("Deleted Deadline check.")).toBeVisible();
  await expect(page.getByLabel("Saved in this browser")).toHaveCount(0);

  await page.setViewportSize({ width: 390, height: 844 });
  const overflowState = await page.evaluate(() => ({
    innerWidth: window.innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
    elements: Array.from(document.querySelectorAll("body *"))
      .map((element) => {
        const rect = element.getBoundingClientRect();
        return {
          tag: element.tagName,
          className: element.className,
          text: element.textContent?.trim().slice(0, 80),
          left: Math.round(rect.left),
          right: Math.round(rect.right),
          width: Math.round(rect.width),
        };
      })
      .filter((element) => element.right > window.innerWidth + 1),
  }));
  expect(
    overflowState.scrollWidth,
    JSON.stringify(overflowState.elements.slice(0, 12), null, 2),
  ).toBeLessThanOrEqual(overflowState.innerWidth);
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export CSV" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe(
    "wbb-2025-26-points-alice-adams-v-bobbi-brown.csv",
  );
});
