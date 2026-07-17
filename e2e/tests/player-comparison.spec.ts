import { expect, test } from "@playwright/test";

test("player comparison keeps shared filters, evidence, and export together", async ({
  page,
}) => {
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
      player_id: number;
      season: string;
      stat_key: string;
      conference_scope: string;
      venue_scope: string;
    };
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

  await page.goto("/workspace/compare");

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
