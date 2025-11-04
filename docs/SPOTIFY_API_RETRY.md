# Spotify API Retry mit Exponential Backoff

**Since:** v1.0 (bereits implementiert), v1.3.8 (dokumentiert & getestet)  
**Gap:** #4 der kritischen Code-Review-Lücken  
**Status:** ✅ Vollständig implementiert & getestet

---

## Übersicht

SpotiPi nutzt **urllib3.util.Retry** für automatische Wiederholungen bei transienten Spotify-API-Fehlern. Dies verhindert, dass temporäre Netzwerkprobleme oder Server-Überlastung zu failed Alarms führen.

### Vorteile

- ✅ **Automatische Wiederholung**: 429, 500, 502, 503, 504 werden automatisch wiederholt
- ✅ **Exponential Backoff**: Wartezeit verdoppelt sich bei jedem Retry (0.6s → 1.2s → 2.4s → ...)
- ✅ **Rate Limit Respect**: Respektiert `Retry-After` Header bei 429 (Too Many Requests)
- ✅ **Kein Retry bei Client-Errors**: 400, 401, 403, 404 werden nicht wiederholt
- ✅ **Thread-safe**: Jeder Thread bekommt eine eigene Session-Instanz
- ✅ **Konfigurierbar**: Alle Parameter via Environment-Variablen anpassbar

---

## Konfiguration

### Standard-Werte

```python
# src/api/http.py (Zeile 98-113)
status_forcelist = [429, 500, 502, 503, 504]
backoff_factor = 0.6  # Default, env: SPOTIPI_HTTP_BACKOFF_FACTOR
total = 5  # Max retries, env: SPOTIPI_HTTP_RETRY_TOTAL
connect = 3  # Connect retries, env: SPOTIPI_HTTP_RETRY_CONNECT
read = 4  # Read retries, env: SPOTIPI_HTTP_RETRY_READ
respect_retry_after_header = True
```

### Environment-Variablen

| Variable | Default | Beschreibung |
|----------|---------|--------------|
| `SPOTIPI_HTTP_BACKOFF_FACTOR` | `0.6` | Backoff-Multiplikator für exponentielle Wartezeit |
| `SPOTIPI_HTTP_RETRY_TOTAL` | `5` | Maximale Anzahl Retries (über alle Typen) |
| `SPOTIPI_HTTP_RETRY_CONNECT` | `3` | Retries bei Connection-Fehlern |
| `SPOTIPI_HTTP_RETRY_READ` | `4` | Retries bei Read-Timeouts |
| `SPOTIPI_HTTP_POOL_CONNECTIONS` | `10` | Max. gleichzeitige Connections |
| `SPOTIPI_HTTP_POOL_MAXSIZE` | `20` | Max. Connection-Pool-Größe |

**Beispiel:**
```bash
# Aggressiveres Retry für schlechte Netzwerke
export SPOTIPI_HTTP_RETRY_TOTAL=8
export SPOTIPI_HTTP_BACKOFF_FACTOR=1.0

# Konservativeres Retry für gute Netzwerke
export SPOTIPI_HTTP_RETRY_TOTAL=3
export SPOTIPI_HTTP_BACKOFF_FACTOR=0.3
```

---

## Retry-Logik

### HTTP-Status-Codes

**Retry (Transiente Fehler):**
- `429 Too Many Requests` → Respektiert `Retry-After` Header
- `500 Internal Server Error` → Server-seitiger Fehler
- `502 Bad Gateway` → Proxy/Gateway-Problem
- `503 Service Unavailable` → Server überlastet
- `504 Gateway Timeout` → Upstream-Timeout

**Kein Retry (Permanente Fehler):**
- `400 Bad Request` → Ungültige Anfrage (Client-Fehler)
- `401 Unauthorized` → Token ungültig (separat behandelt)
- `403 Forbidden` → Fehlende Berechtigung
- `404 Not Found` → Ressource existiert nicht
- `405 Method Not Allowed` → Falsche HTTP-Methode

### Backoff-Berechnung

**Formel:** `{backoff_factor} * (2 ** ({attempt} - 1))`

**Beispiel** (backoff_factor=0.6):
- Attempt 1: 0.6 * (2^0) = **0.6s**
- Attempt 2: 0.6 * (2^1) = **1.2s**
- Attempt 3: 0.6 * (2^2) = **2.4s**
- Attempt 4: 0.6 * (2^3) = **4.8s**
- Attempt 5: 0.6 * (2^4) = **9.6s**

**Total Zeit bei 5 Retries:** ~18.6 Sekunden

---

## Verwendung

### Automatisch (Standard)

Alle Spotify-API-Calls nutzen automatisch die Retry-Logik:

```python
from src.api.spotify import get_playlists, start_playback

# Retries automatisch bei 429, 503, etc.
playlists = get_playlists()

# Playback-Start mit automatischem Retry
start_playback(
    device_id="abc123",
    context_uri="spotify:playlist:xyz"
)
```

### Manuell (Custom Requests)

```python
from src.api.http import SESSION

# SESSION hat bereits Retry-Config
response = SESSION.get(
    "https://api.spotify.com/v1/me",
    headers={"Authorization": f"Bearer {token}"},
    timeout=(4.0, 15.0)
)

# Bei 503 wird automatisch 1-5x wiederholt
if response.status_code == 200:
    data = response.json()
```

### Retry deaktivieren (für spezielle Fälle)

```python
import requests

# Erstelle Session ohne Retry
session = requests.Session()
response = session.get("https://api.spotify.com/v1/me")
```

---

## Monitoring & Debugging

### Log-Ausgabe

Bei aktiviertem Debug-Logging (SPOTIPI_LOG_LEVEL=DEBUG):

```
INFO: HTTP session configured
  http.timeout_connect=4.0
  http.timeout_read=15.0
  http.retry_total=5
  http.pool_connections=10
  http.pool_maxsize=20

DEBUG: Request GET https://api.spotify.com/v1/me/playlists
DEBUG: Response 503 Service Unavailable (attempt 1/5)
DEBUG: Retry in 0.6s (backoff=0.6, attempt=1)
DEBUG: Request GET https://api.spotify.com/v1/me/playlists (retry 1)
DEBUG: Response 200 OK
```

### JSON-Logs (Production)

Mit `SPOTIPI_JSON_LOGS=1`:

```json
{
  "timestamp": "2025-11-04T15:23:45Z",
  "level": "WARNING",
  "logger": "spotify.http",
  "message": "Spotify API rate limit hit, retrying",
  "status_code": 429,
  "retry_after": "2",
  "attempt": 1,
  "max_retries": 5
}
```

---

## Performance-Implikationen

### Overhead

- **Keine zusätzliche Latenz** bei erfolgreichen Requests
- **Erhöhte Latenz** nur bei tatsächlichen Fehlern (gewollt)
- **Memory Overhead**: Negligible (~1KB pro Session)

### Best Practices

1. **Timeouts setzen**: Verhindere hängende Connections
   ```python
   response = SESSION.get(url, timeout=(4.0, 15.0))  # connect, read
   ```

2. **Retry-Count anpassen**: Für Alarm-kritische Requests höhere Werte
   ```bash
   SPOTIPI_HTTP_RETRY_TOTAL=8  # Für Alarm-Playback
   ```

3. **Backoff erhöhen**: Bei häufigen Rate-Limits
   ```bash
   SPOTIPI_HTTP_BACKOFF_FACTOR=1.0  # Längere Wartezeiten
   ```

---

## Problembehandlung

### Zu viele Retries (langsam)

**Symptom:** Requests dauern sehr lang (>30s)

**Lösung:**
```bash
export SPOTIPI_HTTP_RETRY_TOTAL=3
export SPOTIPI_HTTP_BACKOFF_FACTOR=0.4
```

### Zu wenige Retries (flaky)

**Symptom:** Alarm startet nicht trotz funktionierendem Spotify

**Lösung:**
```bash
export SPOTIPI_HTTP_RETRY_TOTAL=8
export SPOTIPI_HTTP_BACKOFF_FACTOR=0.8
```

### Rate-Limit-Errors trotz Retry

**Symptom:** Noch immer 429-Fehler nach Retries

**Ursache:** Zu viele parallele Requests oder kurze Abstände

**Lösung:**
1. Reduziere Parallelität: `SPOTIPI_MAX_CONCURRENCY=2`
2. Erhöhe Backoff: `SPOTIPI_HTTP_BACKOFF_FACTOR=1.5`
3. Prüfe auf Loops/excessive Polling

---

## Testing

### Unit Tests

```bash
source .venv/bin/activate
python -m pytest tests/test_spotify_retry.py -v
```

**Testabdeckung:**
- ✅ Retry-Konfiguration (Status-Codes, Backoff, Max-Attempts)
- ✅ Session-Setup (HTTPS/HTTP-Adapter, Thread-Local)
- ✅ Exponential Backoff-Berechnung
- ✅ Environment-Variable-Konfiguration
- ✅ Thread-Safety

**Ergebnis:** 16 Tests ✅, 2 skipped (Integration/Performance)

### Integration-Test (manuell)

```python
# Simuliere 503-Fehler via Mock-Server
import time
from src.api.http import SESSION

# Erster Request schlägt fehl (503), zweiter erfolgt
start = time.time()
response = SESSION.get("https://httpstat.us/503,200")
elapsed = time.time() - start

# Sollte ~0.6s dauern (1 Retry mit backoff=0.6)
assert elapsed >= 0.5
assert response.status_code == 200
```

---

## Roadmap

- [x] **v1.0**: Retry-Mechanismus mit urllib3
- [x] **v1.3.8**: Tests & Dokumentation
- [ ] **v1.4.0**: Circuit-Breaker für häufige Failures
- [ ] **v1.4.0**: Metrics (erfolgreiche/failed Retries)
- [ ] **v1.5.0**: Adaptive Backoff basierend auf API-Response-Zeiten

---

## Siehe auch

- [ENVIRONMENT_VARIABLES.md](ENVIRONMENT_VARIABLES.md) - Alle SPOTIPI_HTTP_* Flags
- [JSON_LOGGING.md](JSON_LOGGING.md) - Strukturiertes Logging für Retry-Events
- [CONFIG_SCHEMA_VALIDATION.md](CONFIG_SCHEMA_VALIDATION.md) - Config-Validierung

---

**Version:** 1.0  
**Autor:** SpotiPi Team  
**Letzte Änderung:** 2025-11-04
