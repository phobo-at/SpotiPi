import { mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import esbuild from "esbuild";

const __dirname = dirname(fileURLToPath(import.meta.url));
const rootDir = resolve(__dirname, "..");
const watchMode = process.argv.includes("--watch");
const devMode = process.argv.includes("--dev");

const buildOptions = {
  entryPoints: [resolve(rootDir, "frontend/src/main.tsx")],
  outfile: resolve(rootDir, "static/dist/app.js"),
  bundle: true,
  format: "esm",
  platform: "browser",
  target: ["es2020"],
  jsx: "automatic",
  jsxImportSource: "preact",
  sourcemap: devMode ? "inline" : false,
  minify: !devMode,
  legalComments: "none",
  define: {
    "process.env.NODE_ENV": JSON.stringify(devMode ? "development" : "production")
  },
  logLevel: "info"
};

await mkdir(resolve(rootDir, "static/dist"), { recursive: true });

if (watchMode) {
  const context = await esbuild.context(buildOptions);
  await context.watch();
  console.log("Watching frontend sources...");
} else {
  await esbuild.build(buildOptions);
  console.log("Built static/dist/app.js");
}
