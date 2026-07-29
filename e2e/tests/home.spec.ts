import { expect, test } from "@playwright/test";

test("pipeline homepage renders ingest form", async ({ page }) => {
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
    page.getByRole("heading", { name: "Games desk" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Ingest", exact: true })).toBeVisible();
});
