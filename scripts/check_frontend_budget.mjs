import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { gzipSync } from "node:zlib";

const __dirname = dirname(fileURLToPath(import.meta.url));
const rootDir = resolve(__dirname, "..");

const BUDGETS = {
  jsGzipBytes: 45 * 1024,
  cssGzipBytes: 12 * 1024,
  jsRawBytes: 160 * 1024,
  cssRawBytes: 48 * 1024
};

function formatBytes(value) {
  return `${(value / 1024).toFixed(1)} KiB`;
}

async function readAssetSize(relativePath) {
  const absolutePath = resolve(rootDir, relativePath);
  const content = await readFile(absolutePath);
  return {
    rawBytes: content.byteLength,
    gzipBytes: gzipSync(content, { level: 9 }).byteLength
  };
}

async function main() {
  const js = await readAssetSize("static/dist/app.js");
  const css = await readAssetSize("static/dist/app.css");

  const checks = [
    {
      label: "app.js raw",
      value: js.rawBytes,
      budget: BUDGETS.jsRawBytes
    },
    {
      label: "app.js gzip",
      value: js.gzipBytes,
      budget: BUDGETS.jsGzipBytes
    },
    {
      label: "app.css raw",
      value: css.rawBytes,
      budget: BUDGETS.cssRawBytes
    },
    {
      label: "app.css gzip",
      value: css.gzipBytes,
      budget: BUDGETS.cssGzipBytes
    }
  ];

  let failed = false;
  for (const check of checks) {
    const pass = check.value <= check.budget;
    if (!pass) {
      failed = true;
    }
    const status = pass ? "PASS" : "FAIL";
    console.log(
      `[${status}] ${check.label}: ${formatBytes(check.value)} (budget ${formatBytes(check.budget)})`
    );
  }

  if (failed) {
    process.exitCode = 1;
  } else {
    console.log("Frontend budget checks passed.");
  }
}

await main();
