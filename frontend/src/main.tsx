/** @jsxImportSource preact */
import { render } from "preact";

import { App } from "./app";
import type { AppBootstrap } from "./lib/types";
import "./styles.css";

function readBootstrap(): AppBootstrap {
  const element = document.getElementById("spotipi-bootstrap");
  if (!element?.textContent) {
    throw new Error("Missing frontend bootstrap payload");
  }

  return JSON.parse(element.textContent) as AppBootstrap;
}

const root = document.getElementById("app-root");

if (!root) {
  throw new Error("Missing app root");
}

render(<App bootstrap={readBootstrap()} />, root);
