const AxeBuilder = require("@axe-core/playwright").default;
const { expect, test } = require("@playwright/test");

const BOOTSTRAP_SCRIPT_RE = /(<script id="spotipi-bootstrap" type="application\/json">)([\s\S]*?)(<\/script>)/;

async function gotoWithDashboardOverride(page, overrideDashboard) {
  await page.route("**/*", async (route, request) => {
    const url = new URL(request.url());
    if (request.resourceType() !== "document" || url.pathname !== "/") {
      await route.continue();
      return;
    }

    const response = await route.fetch();
    const html = await response.text();
    const match = html.match(BOOTSTRAP_SCRIPT_RE);
    if (!match) {
      await route.fulfill({ response, body: html });
      return;
    }

    const bootstrap = JSON.parse(match[2]);
    bootstrap.dashboard = overrideDashboard(bootstrap.dashboard);
    const bootstrapJson = JSON.stringify(bootstrap).replace(/</g, "\\u003c");
    const patchedHtml = html.replace(BOOTSTRAP_SCRIPT_RE, `$1${bootstrapJson}$3`);
    await route.fulfill({ response, body: patchedHtml });
  });

  await page.goto("/");
}

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

test("player keeps idle copy when playback snapshot is stale but already hydrated", async ({ page }) => {
  await gotoWithDashboardOverride(page, (dashboard) => ({
    ...dashboard,
    playback_status: "empty",
    playback: {
      ...dashboard.playback,
      current_track: null,
      is_playing: false
    },
    hydration: {
      ...dashboard.hydration,
      playback: {
        ...dashboard.hydration.playback,
        pending: true,
        has_data: true
      }
    }
  }));

  const playerCard = page.getByTestId("player-card");
  await expect(playerCard).not.toContainText(/spotify is waking up|spotify wacht auf/i);
  await expect(playerCard).toContainText(/ready to play|bereit zum abspielen|no active playback|keine aktive wiedergabe/i);
});

test("player shows waking copy only during initial playback hydration", async ({ page }) => {
  await gotoWithDashboardOverride(page, (dashboard) => ({
    ...dashboard,
    playback_status: "pending",
    playback: {
      ...dashboard.playback,
      current_track: null,
      is_playing: false
    },
    hydration: {
      ...dashboard.hydration,
      playback: {
        ...dashboard.hydration.playback,
        pending: true,
        has_data: false
      }
    }
  }));

  await expect(page.getByTestId("player-card")).toContainText(/spotify is waking up|spotify wacht auf/i);
});
