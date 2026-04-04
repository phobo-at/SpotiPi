# Raspberry Pi Deployment Script

Local Pi deployment settings are kept out of git.

## Files

- `deploy_to_pi.sh.example` - tracked, anonymized template
- `deploy_to_pi.sh` - local script copy (ignored by git)

## Setup

1. Create your local script from the template:

```bash
cp scripts/deploy_to_pi.sh.example scripts/deploy_to_pi.sh
chmod +x scripts/deploy_to_pi.sh
```

2. Optional: adjust defaults in `scripts/deploy_to_pi.sh`  
   Recommended: keep the template unchanged and set env vars when needed.

3. Verify SSH connectivity:

```bash
ssh pi@your-pi-host.local "echo 'Connection OK'"
```

4. Deploy:

```bash
./scripts/deploy_to_pi.sh
```

## Useful overrides

```bash
SPOTIPI_PI_HOST=pi@192.168.1.100 ./scripts/deploy_to_pi.sh
SPOTIPI_PI_PATH=/opt/spotipi ./scripts/deploy_to_pi.sh
SPOTIPI_FORCE_SYSTEMD=1 ./scripts/deploy_to_pi.sh
SPOTIPI_PURGE_UNUSED=1 ./scripts/deploy_to_pi.sh
```

## Notes

- Uses `rsync` with a runtime allowlist.
- Supports optional systemd sync and service restart.
- Prints a compact deployment summary after sync.
