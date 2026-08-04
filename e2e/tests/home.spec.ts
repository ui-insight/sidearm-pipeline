import { expect, test } from "@playwright/test";

test("post-login landing page introduces the project and opens the demo", async ({ page }) => {
  await page.route("**/api/v1/auth/session", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        authenticated: true,
        username: "e2e-user",
        roles: [],
      }),
    });
  });

  await page.goto("/");

  await expect(
    page.getByRole("heading", {
      name: "One trusted place to find the facts behind every game.",
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Available in this prototype" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Start the Athletics demo" }),
  ).toHaveAttribute("href", "/demo");
});

test("games desk remains available from its own route", async ({ page }) => {
  await page.route("**/api/v1/auth/session", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        authenticated: true,
        username: "e2e-user",
        roles: [],
      }),
    });
  });

  await page.route("**/api/v1/games", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    });
  });

  await page.goto("/games");

  await expect(page.getByRole("heading", { name: "Games desk" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Ingest", exact: true })).toBeVisible();
});
