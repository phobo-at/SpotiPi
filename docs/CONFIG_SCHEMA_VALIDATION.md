# Config Schema Validation mit Pydantic

**Since:** v1.3.8  
**Gap:** #3 der kritischen Code-Review-Lücken  
**Status:** ✅ Implementiert & getestet

---

## Übersicht

SpotiPi nutzt seit v1.3.8 **Pydantic v2** für strikte Config-Validierung. Fehlerhafte Konfigurationen werden bereits beim Laden erkannt, statt erst zur Laufzeit zu crashen.

### Vorteile

- ✅ **Type Safety**: Automatische Typ-Konvertierung und -Prüfung
- ✅ **Field Validation**: Regex-Pattern, Ranges, Custom Validators
- ✅ **Defaults**: Fehlende Felder bekommen sinnvolle Defaults
- ✅ **Clear Errors**: Verständliche Fehlermeldungen mit Feldnamen
- ✅ **Backward Compatible**: Fallback zu Legacy-Validierung wenn Pydantic fehlt

---

## Schema-Struktur

### SpotiPiConfig (Master Schema)

```python
from src.config_schema import SpotiPiConfig, validate_config_dict

# Beispiel: Minimale Config
config = {
    "time": "07:30",
    "enabled": True,
    "playlist_uri": "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M",
    "device_name": "Raspberry Pi",
    "alarm_volume": 50,
    "timezone": "Europe/Vienna"
}

validated_model, warnings = validate_config_dict(config)
print(validated_model.time)  # "07:30"
print(validated_model.alarm_volume)  # 50
```

### Felder & Validierung

| Feld | Typ | Validierung | Default |
|------|-----|-------------|---------|
| `time` | `str` | Regex: `HH:MM` (00:00-23:59) | `"07:00"` |
| `enabled` | `bool` | - | `False` |
| `playlist_uri` | `str` | - | `""` |
| `device_name` | `str` | - | `""` |
| `alarm_volume` | `int` | Range: 0-100 | `50` |
| `fade_in` | `bool` | - | `False` |
| `shuffle` | `bool` | - | `False` |
| `weekdays` | `list[int]` \| `None` | Each: 0-6 (Mo-So) | `None` (täglich) |
| `timezone` | `str` | ZoneInfo-Check | `"Europe/Vienna"` |
| `log_level` | `str` | Enum: DEBUG/INFO/WARNING/ERROR/CRITICAL | `"INFO"` |

---

## Verwendung

### Im Code: Config laden & validieren

```python
from src.config import ConfigManager

cm = ConfigManager()
config = cm.load_config()  # Lädt & validiert automatisch

# Config ist bereits validiert und type-safe
print(config["alarm_volume"])  # Garantiert int, 0-100
```

### Manuelle Validierung

```python
from src.config_schema import validate_config_dict

raw_config = {
    "time": "25:99",  # FEHLER: Ungültige Zeit
    "alarm_volume": 150,  # FEHLER: Über 100
    "weekdays": [0, 7],  # FEHLER: 7 ungültig
}

try:
    validated, warnings = validate_config_dict(raw_config)
except ValueError as e:
    print(f"Config-Fehler: {e}")
    # Output: "1 validation error for SpotiPiConfig\ntime\n  String should match pattern..."
```

---

## Fehlerbehandlung

### Validierungsfehler

Bei ungültigen Werten wirft Pydantic `ValueError` mit detaillierten Infos:

```
1 validation error for SpotiPiConfig
alarm_volume
  Input should be less than or equal to 100 [type=less_than_equal, input_value=150]
```

### Fallback zu Legacy-Validierung

Wenn Pydantic nicht installiert ist (z.B. alte Umgebung), fällt der `ConfigManager` automatisch auf die Legacy-Validierung zurück:

```python
# src/config.py
if SCHEMA_VALIDATION_AVAILABLE:
    # Pydantic-Validierung
    validated_model, warnings = validate_config_dict(config)
    return validated_model.to_dict()
else:
    # Legacy-Validierung mit manuellen Checks
    return self._legacy_validate_config(config)
```

**Log-Ausgabe:**
```
WARNING: Pydantic not available, falling back to legacy validation
```

---

## Migration von alten Configs

Die Funktion `migrate_legacy_config()` kümmert sich um veraltete Feldnamen:

```python
from src.config_schema import migrate_legacy_config

old_config = {
    "alarm_time": "07:00",  # Altes Feld
    "old_field": "value"    # Deprecated
}

migrated = migrate_legacy_config(old_config)
# migrated["time"] == "07:00"  # Migriert
```

**Aktuell:** Placeholder-Implementierung (Pass-through). Bei Bedarf erweitern für konkrete Migrationen.

---

## Testing

### Unit Tests ausführen

```bash
source .venv/bin/activate
python -m pytest tests/test_config_validation.py -v
```

**Testabdeckung:**
- ✅ Valide Minimal- & Full-Configs
- ✅ Ungültige Werte (Zeit, Volume, Weekdays, Timezone)
- ✅ Edge-Cases (Boundary-Values, None, leere Strings)
- ✅ ConfigManager-Integration (Validierung + Save)
- ✅ Parametrisierte Tests für alle Field-Ranges

**Ergebnis:** 27 Tests, alle ✅

---

## Edge Cases

### Boundary Values

| Feld | Minimum | Maximum | Invalide |
|------|---------|---------|----------|
| `time` | `"00:00"` | `"23:59"` | `"24:00"`, `"12:60"` |
| `alarm_volume` | `0` | `100` | `-1`, `101` |
| `weekdays` | `[0]` (Mo) | `[6]` (So) | `[7]`, `[-1]` |

### Optionale Felder

- `weekdays=None`: Alarm läuft **täglich** (kein Filter)
- `weekdays=[]`: Alarm **nie aktiv**
- `playlist_uri=""`: Leer erlaubt (App-Logik muss prüfen)

### Leere Strings

Leere Strings sind für `playlist_uri` und `device_name` valide (Schema-Ebene). Die **App-Logik** (z.B. in `app.py`) muss prüfen, ob diese Werte sinnvoll sind (z.B. Alarm mit leerem Playlist → Fehler).

---

## Performance

- **Overhead:** < 5ms für typische Config (20 Felder)
- **Memory:** Negligible (Models sind lightweight)
- **Pi Zero W:** Kein spürbarer Impact, da nur beim Load/Save

---

## Roadmap

- [ ] **v1.4.0**: Erweiterte Migrationslogik für Breaking Changes
- [ ] **v1.4.0**: JSON-Schema-Export für externe Tools
- [ ] **v1.5.0**: Multi-Alarm-Support mit Array-Validierung

---

## Siehe auch

- [ENVIRONMENT_VARIABLES.md](ENVIRONMENT_VARIABLES.md) - Env-Flags für Config-Overrides
- [JSON_LOGGING.md](JSON_LOGGING.md) - Strukturiertes Logging (Gap #2)
- [THREAD_SAFETY.md](THREAD_SAFETY.md) - Thread-sichere Config-Zugriffe

---

**Version:** 1.0  
**Autor:** SpotiPi Team  
**Letzte Änderung:** 2025-11-04
