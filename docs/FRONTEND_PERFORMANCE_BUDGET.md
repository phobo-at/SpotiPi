# Frontend Performance Budget (Pi Zero W)

This budget is enforced by `npm run budget:check` and Playwright runtime tests.

## Asset Budget

- `static/dist/app.js` raw: **<= 160 KiB**
- `static/dist/app.js` gzip: **<= 45 KiB**
- `static/dist/app.css` raw: **<= 48 KiB**
- `static/dist/app.css` gzip: **<= 12 KiB**

## Runtime Budget (dashboard initial load)

- API calls during initial load window: **<= 4**
- `domInteractive` (TTI proxy): **<= 7000 ms**
- Legacy runtime requests (`/static/js/main.js`, `/static/js/modules/*`): **0**

## Validation

Run all mandatory gates:

```bash
npm run typecheck
npm run build
npm run budget:check
npm run test:e2e
pytest -q
```
