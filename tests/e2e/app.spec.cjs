const AxeBuilder = require("@axe-core/playwright").default;
const { expect, test } = require("@playwright/test");

const BOOTSTRAP_SCRIPT_RE = /(<script id="spotipi-bootstrap" type="application\/json">)([\s\S]*?)(<\/script>)/;

async function gotoWithBootstrapOverride(page, overrideBootstrap) {
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
    const nextBootstrap = overrideBootstrap(bootstrap);
    const bootstrapJson = JSON.stringify(nextBootstrap).replace(/</g, "\\u003c");
    const patchedHtml = html.replace(BOOTSTRAP_SCRIPT_RE, `$1${bootstrapJson}$3`);
    await route.fulfill({ response, body: patchedHtml });
  });

  await page.goto("/");
}

async function gotoWithDashboardOverride(page, overrideDashboard) {
  await gotoWithBootstrapOverride(page, (bootstrap) => ({
    ...bootstrap,
    dashboard: overrideDashboard(bootstrap.dashboard)
  }));
}

test("dashboard shell renders primary surfaces without critical accessibility issues", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByTestId("player-card")).toBeVisible();
  await expect(page.getByTestId("alarm-card")).toBeVisible();
  await expect(page.getByTestId("play-card")).toBeVisible();

  const results = await new AxeBuilder({ page }).analyze();
  const blockingViolations = results.violations.filter((violation) =>
    ["serious", "critical"].includes(violation.impact || "")
  );

  expect(blockingViolations).toEqual([]);
});

test("sleep tiles are hidden when sleep feature is disabled", async ({ page }) => {
  await gotoWithBootstrapOverride(page, (bootstrap) => ({
    ...bootstrap,
    settings: {
      ...bootstrap.settings,
      feature_flags: {
        ...bootstrap.settings.feature_flags,
        sleep_timer: false
      }
    }
  }));

  await expect(page.getByTestId("sleep-card")).toHaveCount(0);
  await expect(page.getByTestId("sleep-snapshot")).toHaveCount(0);
});

test("sleep tiles are visible when sleep feature is enabled", async ({ page }) => {
  await gotoWithBootstrapOverride(page, (bootstrap) => ({
    ...bootstrap,
    settings: {
      ...bootstrap.settings,
      feature_flags: {
        ...bootstrap.settings.feature_flags,
        sleep_timer: true
      }
    }
  }));

  await expect(page.getByTestId("sleep-card")).toBeVisible();
  await expect(page.getByTestId("sleep-snapshot")).toBeVisible();
});

test("settings surface opens from the header action", async ({ page }) => {
  await page.goto("/");

  await page.getByTestId("settings-trigger").click();
  await expect(page.getByTestId("settings-sheet")).toBeVisible();
});

test("settings surface exposes Spotify credential controls", async ({ page }) => {
  await page.goto("/");

  await page.getByTestId("settings-trigger").click();
  await expect(page.getByTestId("settings-sheet")).toBeVisible();
  await expect(page.locator("#spotify-client-id")).toBeVisible();
  await expect(page.locator("#spotify-client-secret")).toBeVisible();
  await expect(page.locator("#spotify-refresh-token")).toBeVisible();
  await expect(page.getByRole("button", { name: /connect spotify|mit spotify verbinden/i })).toBeVisible();
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
  await expect.poll(async () => page.evaluate(() => {
    const active = document.activeElement;
    const dialog = document.querySelector("#alarm-sheet");
    return Boolean(active && dialog && dialog.contains(active));
  })).toBeTruthy();

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

test("open sheet locks document scroll and uses internal sheet scroll container", async ({ page }) => {
  await page.goto("/");

  await page.getByTestId("settings-trigger").click();
  await expect(page.getByTestId("settings-sheet")).toBeVisible();
  await expect.poll(async () => page.evaluate(() => getComputedStyle(document.body).overflow)).toBe("hidden");
  await expect.poll(async () => page.evaluate(() => getComputedStyle(document.documentElement).overflow)).toBe("hidden");

  const styles = await page.evaluate(() => {
    const sheetBody = document.querySelector("#settings-sheet .sheet-body");
    const sheetBackdrop = document.querySelector(".sheet-backdrop");
    return {
      bodyOverflow: getComputedStyle(document.body).overflow,
      htmlOverflow: getComputedStyle(document.documentElement).overflow,
      sheetBodyOverflowY: sheetBody ? getComputedStyle(sheetBody).overflowY : "",
      backdropOverflow: sheetBackdrop ? getComputedStyle(sheetBackdrop).overflow : ""
    };
  });

  expect(styles.bodyOverflow).toBe("hidden");
  expect(styles.htmlOverflow).toBe("hidden");
  expect(["auto", "scroll"]).toContain(styles.sheetBodyOverflowY);
  expect(styles.backdropOverflow).toBe("hidden");
});

test("settings sheet content does not overflow horizontally on small screens", async ({ page }) => {
  await page.goto("/");

  await page.getByTestId("settings-trigger").click();
  await expect(page.getByTestId("settings-sheet")).toBeVisible();

  const overflowing = await page.evaluate(() => {
    const selectors = [
      "#settings-sheet .sheet-header",
      "#settings-sheet .sheet-body",
      "#settings-sheet .sheet-stack",
      "#settings-sheet .settings-group",
      "#settings-sheet .account-card",
      "#settings-sheet .sheet-actions",
      "#settings-sheet .toggle-field"
    ];

    return selectors.flatMap((selector) =>
      Array.from(document.querySelectorAll(selector)).flatMap((element) => {
        const htmlElement = /** @type {HTMLElement} */ (element);
        const style = getComputedStyle(htmlElement);
        if (style.display === "none" || style.visibility === "hidden") {
          return [];
        }

        if (htmlElement.scrollWidth <= htmlElement.clientWidth + 1) {
          return [];
        }

        return [`${selector}:${htmlElement.scrollWidth}>${htmlElement.clientWidth}`];
      })
    );
  });

  expect(overflowing).toEqual([]);
});

test("credential toggles switch aria-pressed and stored preview value", async ({ page }) => {
  await page.route("**/api/settings/spotify", async (route) => {
    const response = await route.fetch();
    const payload = await response.json();
    payload.data.credentials.client_id.set = true;
    payload.data.credentials.client_id.value = "demo-client-id-1234";
    payload.data.credentials.client_id.masked = "demo...1234";
    payload.data.credentials.client_secret.set = true;
    payload.data.credentials.client_secret.masked = "abcd...wxyz";
    payload.data.credentials.refresh_token.set = true;
    payload.data.credentials.refresh_token.masked = "tokn...z999";
    await route.fulfill({ response, json: payload });
  });

  await page.goto("/");
  await page.getByTestId("settings-trigger").click();
  await expect(page.getByTestId("settings-sheet")).toBeVisible();

  const clientIdToggle = page.locator('button[aria-controls*="spotify-client-id"]');
  const clientIdDisplay = page.locator("#spotify-client-id-display");
  const secretToggle = page.locator('button[aria-controls*="spotify-client-secret"]');
  const secretDisplay = page.locator("#spotify-client-secret-display");

  await expect(clientIdDisplay).toHaveText("************");
  await expect(clientIdToggle).toHaveAttribute("aria-pressed", "false");
  await expect(secretToggle).toHaveAttribute("aria-pressed", "false");
  await expect(secretDisplay).toHaveText("************");

  await clientIdToggle.click();
  await expect(clientIdToggle).toHaveAttribute("aria-pressed", "true");
  await expect(clientIdDisplay).toHaveText("demo-client-id-1234");

  await secretToggle.click();
  await expect(secretToggle).toHaveAttribute("aria-pressed", "true");
  await expect(secretDisplay).toHaveText("abcd...wxyz");
});

test("library picker supports keyboard tab switching and offline retry state", async ({ page }) => {
  await page.goto("/");

  await page.locator('[data-testid="play-card"] button').click();
  await expect(page.locator("#play-sheet")).toBeVisible();
  await expect(page.getByRole("button", { name: /start playback|wiedergabe starten/i })).toHaveCount(0);

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

test("search tab does not refetch unchanged query on unrelated rerenders", async ({ page }) => {
  let searchCalls = 0;

  await page.route("**/api/music-search**", async (route) => {
    searchCalls += 1;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        success: true,
        timestamp: "2026-01-01T00:00:00.000Z",
        request_id: `search-${searchCalls}`,
        data: {
          query: "red ho",
          types: ["track", "album", "artist", "playlist"],
          results: {
            tracks: [
              {
                uri: "spotify:track:1",
                name: "Can't Stop",
                artist: "Red Hot Chili Peppers",
                type: "track"
              }
            ],
            albums: [],
            artists: [],
            playlists: []
          },
          total: 1
        }
      })
    });
  });

  await page.goto("/");
  await page.locator('[data-testid="play-card"] button').click();
  await expect(page.locator("#play-sheet")).toBeVisible();

  const searchTab = page.locator("#library-tab-search");
  await searchTab.click();
  await expect(searchTab).toHaveAttribute("aria-selected", "true");
  await page.waitForTimeout(350);
  const searchInput = page.locator("#play-sheet input[type='search']");
  await searchInput.fill("red ho");

  await expect.poll(() => searchCalls, { timeout: 10000 }).toBe(1);
  await page.waitForTimeout(2600);

  expect(searchCalls).toBe(1);
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

test("player shows dummy cover when no artwork is available", async ({ page }) => {
  await gotoWithDashboardOverride(page, (dashboard) => ({
    ...dashboard,
    playback_status: "empty",
    playback: {
      ...dashboard.playback,
      current_track: null,
      is_playing: false
    }
  }));

  await expect(page.getByTestId("player-fallback-artwork")).toBeVisible();
});

test("player shows track artwork when image is available", async ({ page }) => {
  await gotoWithDashboardOverride(page, (dashboard) => ({
    ...dashboard,
    playback_status: "ready",
    playback: {
      ...dashboard.playback,
      current_track: {
        name: "Demo Track",
        artist: "Demo Artist",
        album_image: "https://example.com/cover.jpg"
      },
      is_playing: true
    }
  }));

  await expect(page.getByTestId("player-fallback-artwork")).toHaveCount(0);
  await expect(page.locator("[data-testid='player-card'] .player-artwork img")).toBeVisible();
});
