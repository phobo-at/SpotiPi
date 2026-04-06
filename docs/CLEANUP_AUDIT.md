# SpotiPi Repo Cleanup Audit

**Stand:** 2026-04-06 — Read-only Analyse, keine Änderungen durchgeführt.
**Status:** In Arbeit — weitere Analyse ausstehend.

---

## 1) Executive Summary

Das Repo ist insgesamt ordentlich – kein `static/js/modules/`-Legacy mehr (Verzeichnis existiert nicht), keine `.old`/`.bak`-Dateien im Git. Drei Problemzonen wurden identifiziert:

1. **`src/app_factory.py`** ist ein Compatibility-Shim ohne einzige eingehende Import-Referenz — sicher löschbar.
2. **Drei Jinja-Templates** (`alarm.html`, `settings.html`, `sleep.html`) sind im Git und 167–169 Zeilen groß, werden aber nirgends gerendert oder included — sie stammen aus der pre-SPA-Ära.
3. **`static/css/`** (23 Dateien, alle getrackt) wird von keinem Template und nicht vom Build geladen — nur `static/dist/app.css` zieht der SPA-Shell. Vor Löschung ist ein CSS-Overlap-Abgleich mit `frontend/src/styles.css` nötig.
4. **Drei Template-Context-Variablen** in `src/app.py:382–384` (`static_css_path`, `static_js_path`, `static_icons_path`) sind toter Code — nirgends im `index.html` konsumiert.
5. Drei **lokale ungetrackte Artefakte** (`.pdf-venv/`, `output/`, `venv/`) sind kein Git-Problem, aber Clutter.

---

## 2) Kandidaten-Tabelle

| Pfad | Kategorie | Risiko | Begründung | Evidenz |
|------|-----------|--------|------------|---------|
| `src/app_factory.py` | `safe-delete` | low | Wrapper-Shim ohne eingehende Referenz; `run.py` importiert direkt `src.app` | `rg "app_factory"` → 0 Treffer in allen Dateien; `run.py:15`: `from src.app import create_app` |
| `templates/alarm.html` | `likely-delete` | medium | Jinja-Partial, nirgends gerendert oder included; pre-SPA-Relikt | `rg "alarm\.html"` → kein Treffer in `.py`/`.html`; `render_template` in `src/routes/main.py` zeigt nur `index.html` |
| `templates/settings.html` | `likely-delete` | medium | Header-Kommentar „Included in index.html" ist falsch — `index.html` hat keine Jinja-Includes | `rg "settings\.html"` → 0 Treffer; `templates/index.html:1–36` hat keine `include`-Direktiven |
| `templates/sleep.html` | `likely-delete` | medium | Analog zu den anderen Partials; kein Referenznachweis | `rg "sleep\.html"` → 0 Treffer in Code |
| `static/css/` (23 Dateien) | `likely-delete` | high | SPA-Shell lädt nur `static/dist/app.css`; esbuild bundelt nur ab `frontend/src/main.tsx`; `static_css_path` in `app.py:382` wird nicht in `index.html` konsumiert | `templates/index.html:7–9`: nur `dist/app.css`; `scripts/build_frontend.mjs:13`: entryPoint = `main.tsx`; `rg "static/css" templates/` → 0 Treffer |
| `static_css_path`/`static_js_path`/`static_icons_path` in `src/app.py:382–384` | `likely-delete` | low | Template-Context-Vars, die keinem Template übergeben werden (Code, keine Datei) | `rg "static_css_path" templates/` → 0 Treffer; `index.html` konsumiert keines dieser Keys |
| `.pdf-venv/` | `keep` (untracked) | low | Ungetrackt, kein Code-Bezug; lokales Dev-Artefakt. Git-sauber — kein Action-Item | `git ls-files .pdf-venv` → nicht getrackt; `rg "pdf.venv"` → 0 Treffer |
| `output/` | `keep` (untracked) | low | Leeres Verzeichnis (nur `.DS_Store`), ungetrackt | `git ls-files output/` → nicht getrackt |
| `venv/` | `keep` (gitignored) | low | Gitignored Pi-Stil-Venv; `setup_pi.sh` und `deploy/systemd/spotipi.service` referenzieren `venv/` auf dem Pi. Lokal ist `.venv/` aktiv | `.gitignore:20`; `scripts/setup_pi.sh:27`; `deploy/systemd/spotipi.service:15` |
| `src/app.py` (Gesamt) | `keep` | — | Flask-Factory, aktiv in `run.py` | `run.py:15`: `from src.app import create_app` |
| `src/core/scheduler.py` | `keep` | — | Enthält `next_alarm_datetime` + Backward-compat-Klasse; referenziert von `alarm_service.py`, `alarm_scheduler.py`, etc. | `rg "from.*scheduler import"` → 6 Treffer |
| `scripts/run_alarm.sh` | `keep` | — | **Pi-kritisch**: direkt in `deploy/systemd/spotipi-alarm.service:ExecStart` eingetragen | `deploy/systemd/spotipi-alarm.service`: `ExecStart=bash -lc './scripts/run_alarm.sh'` |
| `scripts/toggle_logging.sh` | `keep` | — | Pi-Betriebstool, in `docs/MIGRATION_GUIDE.md:49–51` dokumentiert | `docs/MIGRATION_GUIDE.md:49` |
| `generate_token.py` | `keep` | — | Getestet in `tests/test_generate_token.py`; kritisches Setup-Tool | `tests/test_generate_token.py` (direkter Import) |
| `spoti` | `keep` | — | Operativer Root-Wrapper; in `docs/README_DevServer.md` + `docs/THREAD_SAFETY.md` erwähnt | `docs/README_DevServer.md`; `file spoti` → Shell-Skript |
| `static/dist/` | `keep` | — | Pi-Runtime — kann auf Pi nicht gebaut werden; AGENTS.md:54–55 explizit | `AGENTS.md:54`: „Treat the committed static/dist/ bundle as production runtime input" |
| `deploy/systemd/` | `keep` | — | Pi-kritisch, `deploy/install.sh` und `install_fresh_pi.sh` kopieren Units | `deploy/install.sh:8–16` |
| Alle `src/utils/*.py` | `keep` | — | Alle referenziert (mind. 1 Import-Nachweis je Datei) | Diverse `rg -l` Searches |

---

## 3) Deletion Batches

### Batch A — Low Risk (sicher löschen)

| # | Pfad | Aktion |
|---|------|--------|
| A1 | `src/app_factory.py` | `git rm src/app_factory.py` |

**Bedingung:** `pytest` danach ausführen (kein Test importiert es direkt).

---

### Batch B — Medium Risk (nach manueller Sichtung löschen)

| # | Pfad | Aktion |
|---|------|--------|
| B1 | `templates/alarm.html` | `git rm templates/alarm.html` |
| B2 | `templates/settings.html` | `git rm templates/settings.html` |
| B3 | `templates/sleep.html` | `git rm templates/sleep.html` |
| B4 | `src/app.py:382–384` | Dead Code entfernen (`static_css_path`, `static_js_path`, `static_icons_path`) |

**Bedingung:** Kurze Sichtung, ob die Templates oder Vars irgendwo in Docs, Tests oder externen Scripts referenziert werden — Suche ergab 0 Treffer, aber Batch B braucht GO vor dem ersten Schnitt.

---

### Batch C — High Risk (nur manuell / nach CSS-Audit)

| # | Pfad | Aktion |
|---|------|--------|
| C1 | `static/css/` (23 Dateien) | Erst CSS-Diff: Was steht in `static/css/` und fehlt in `frontend/src/styles.css`? Dann `git rm -r static/css/` |

**Bedingung:** Visueller Vergleich `static/css/` vs. `frontend/src/styles.css` (1 339 Zeilen). Falls Styles vollständig im Bundle aufgegangen sind → sicher. Falls nicht → Portierung vor Löschung.

---

## 4) Validierungsplan nach Löschung

**Nach Batch A:**
```bash
pytest
```

**Nach Batch B (Templates + dead code in app.py):**
```bash
pytest
# Stichprobe: Browser-Test Dashboard, Settings-Route → kein 500
```

**Nach Batch C (static/css/):**
```bash
npm run typecheck && npm run build && npm run budget:check
npm run test:e2e
# Visual-Check: Alle UI-Styles noch intakt (Dashboard, Settings, mobile)
pytest  # Backend unverändert, aber Sanity-Check
```

---

## 5) Offene Fragen / Ausstehende Analysen

- [ ] **CSS-Overlap-Audit:** Wurden alle Styles aus `static/css/` vollständig in `frontend/src/styles.css` übertragen? (Insbesondere `static/css/features/` — `alarm.css`, `devices.css`, `music.css` usw.)
- [ ] **Template Git-History:** `git log -- templates/alarm.html` — wann zuletzt gerendert? Gibt es Feature-Branches die noch darauf zeigen?
- [ ] **`static_css_path` in Bootstrap-Daten:** Wird der Key evtl. vom Frontend (JS) konsumiert, nicht vom Jinja-Template? (Bootstrap-JSON-Payload prüfen)
- [ ] **`src/app_factory.py` externe Nutzung:** Gibt es WSGI-Configs oder externe Tooling-Setups (z. B. Gunicorn/uWSGI-Config) die `src.app_factory:create_app` referenzieren?

---

## Änderungslog

| Datum | Aktion | Ergebnis |
|-------|--------|----------|
| 2026-04-06 | Initiale Analyse (read-only) | Dieses Dokument |
