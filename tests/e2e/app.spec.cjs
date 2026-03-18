const AxeBuilder = require("@axe-core/playwright").default;
const { expect, test } = require("@playwright/test");

test("dashboard shell renders primary surfaces without critical accessibility issues", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByTestId("player-card")).toBeVisible();
  await expect(page.getByTestId("alarm-card")).toBeVisible();
  await expect(page.getByTestId("sleep-card")).toBeVisible();
  await expect(page.getByTestId("play-card")).toBeVisible();

  const results = await new AxeBuilder({ page }).analyze();
  const blockingViolations = results.violations.filter((violation) =>
    ["serious", "critical"].includes(violation.impact || "")
  );

  expect(blockingViolations).toEqual([]);
});

test("settings surface opens from the header action", async ({ page }) => {
  await page.goto("/");

  await page.getByTestId("settings-trigger").click();
  await expect(page.getByTestId("settings-sheet")).toBeVisible();
});

test("alarm flow opens from the primary action card", async ({ page }) => {
  await page.goto("/");

  await page.locator('[data-testid="alarm-card"] button').click();
  await expect(page.getByTestId("alarm-sheet")).toBeVisible();
});
