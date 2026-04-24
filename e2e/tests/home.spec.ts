import { expect, test } from "@playwright/test";

test("pipeline homepage renders ingest form", async ({ page }) => {
  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: "Vandals Stats Pipeline" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: /ingest/i })).toBeVisible();
});
