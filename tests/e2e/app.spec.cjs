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

test("sheet closes with Escape and restores focus to trigger", async ({ page }) => {
  await page.goto("/");

  const trigger = page.getByTestId("settings-trigger");
  await trigger.focus();
  await trigger.click();

  const sheet = page.locator("#settings-sheet");
  await expect(sheet).toBeVisible();

  await expect.poll(async () => page.evaluate(() => {
    const active = document.activeElement;
    const dialog = document.querySelector("#settings-sheet");
    return Boolean(active && dialog && dialog.contains(active));
  })).toBeTruthy();

  await page.keyboard.press("Escape");
  await expect(sheet).toBeHidden();
  await expect.poll(async () => page.evaluate(() => {
    const active = document.activeElement;
    const trigger = document.querySelector('[data-testid="settings-trigger"]');
    return active === trigger;
  })).toBeTruthy();
});

test("sheet traps keyboard focus", async ({ page }) => {
  await page.goto("/");

  await page.locator('[data-testid="alarm-card"] button').click();
  await expect(page.getByTestId("alarm-sheet")).toBeVisible();

  for (let i = 0; i < 20; i += 1) {
    await page.keyboard.press("Tab");
  }

  const focusStaysInside = await page.evaluate(() => {
    const active = document.activeElement;
    const dialog = document.querySelector("#alarm-sheet");
    return Boolean(active && dialog && dialog.contains(active));
  });
  expect(focusStaysInside).toBeTruthy();
});

test("library picker supports keyboard tab switching and offline retry state", async ({ page }) => {
  await page.goto("/");

  await page.locator('[data-testid="play-card"] button').click();
  await expect(page.locator("#play-sheet")).toBeVisible();

  const tabs = page.locator("#play-sheet [role='tab']");
  await tabs.nth(0).evaluate((element) => {
    element.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }));
  });

  await expect(tabs.nth(1)).toHaveAttribute("aria-selected", "true");

  await page.context().setOffline(true);
  await page.evaluate(() => window.dispatchEvent(new Event("offline")));

  const offlineCard = page.locator("#play-sheet .library-picker .state-card");
  await expect(offlineCard).toContainText(/offline|offline-modus/i);
  await offlineCard.getByRole("button").click();
  await expect(offlineCard).toContainText(/offline|offline-modus/i);
});

test("initial load stays within runtime budget and avoids legacy assets", async ({ page }) => {
  const requestUrls = [];
  page.on("requestfinished", (request) => {
    requestUrls.push(request.url());
  });

  await page.goto("/");
  await expect(page.getByTestId("player-card")).toBeVisible();
  await page.waitForTimeout(1800);

  const apiCalls = requestUrls.filter((url) => url.includes("/api/")).length;
  expect(apiCalls).toBeLessThanOrEqual(4);

  const legacyAssetRequests = requestUrls.filter(
    (url) => url.includes("/static/js/main.js") || url.includes("/static/js/modules/")
  );
  expect(legacyAssetRequests).toEqual([]);

  const timing = await page.evaluate(() => {
    const navEntry = performance.getEntriesByType("navigation")[0];
    return navEntry && typeof navEntry.domInteractive === "number"
      ? navEntry.domInteractive
      : 0;
  });

  expect(timing).toBeGreaterThan(0);
  expect(timing).toBeLessThanOrEqual(7000);
});
