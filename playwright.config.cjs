const { defineConfig, devices } = require("@playwright/test");

const baseURL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:5001";

module.exports = defineConfig({
  testDir: "./tests/e2e",
  testMatch: /.*\.spec\.(cjs|js|ts)$/,
  timeout: 30_000,
  retries: process.env.CI ? 2 : 0,
  reporter: "list",
  use: {
    baseURL,
    trace: "on-first-retry",
    screenshot: "only-on-failure"
  },
  webServer: process.env.PLAYWRIGHT_BASE_URL
    ? undefined
    : {
        command: "python3 run.py",
        url: baseURL,
        timeout: 120_000,
        reuseExistingServer: !process.env.CI,
        env: {
          SPOTIPI_DEBUG: "0",
          SPOTIPI_DISABLE_RELOADER: "1",
          SPOTIPI_WARMUP: "0",
          SPOTIPI_ENV: "development"
        }
      },
  projects: [
    {
      name: "mobile",
      use: {
        ...devices["Pixel 7"]
      }
    },
    {
      name: "tablet",
      use: {
        browserName: "chromium",
        viewport: { width: 834, height: 1112 },
        hasTouch: true,
        isMobile: false
      }
    },
    {
      name: "desktop",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 1100 }
      }
    }
  ]
});
