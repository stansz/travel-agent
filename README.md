# Travel Agent ✈️

AI travel assistant chatbot — FastAPI frontend + Pi (Z.AI) brain with 17 travel tools.

## Features

- **Chat UI** — dark-themed web interface with preset queries
- **17 Travel Tools** — flights, hotels, advisories, weather, currency, translation, more
- **Pi Agent** — Z.AI `glm-5-turbo` with bash-only toolset (no coding tools)
- **Podman Quadlet** — single-container deploy, auto-restart

## Deploy

```bash
# Build
podman build -t localhost/travel-agent:latest .

# Install quadlet
cp travel-agent.container ~/.config/containers/systemd/
systemctl --user daemon-reload
systemctl --user start travel-agent.service

# Cloudflare Tunnel
# Route: travel.ogsapps.cc → localhost:8092
```

## Architecture

```
Browser → CF Tunnel → :8092 → FastAPI → Pi (Z.AI glm-5.3-flash, thinking=high)
                                          → travel.py CLI → ~/.hermes/skills/travel/*/scripts → APIs
```

## Mounts (see travel-agent.container)

| Host | Container | Why |
|---|---|---|
| `~/travel-agent/app.py`, `pi-skill.md` | `/app/web/` | app + Pi system prompt |
| `~/.hermes/skills/travel` | `/app/travel` | travel.py + sibling skill scripts |
| `~/travel-agent/travel.py` | `/app/travel/travel-agent/scripts/travel.py` | repo copy shadows the skills copy |
| `~/.hermes/.env` | `/root/.hermes/.env` | API keys (scripts read `$HOME/.hermes/.env`) |
| `~/travel-agent/data` | `/app/data` | sessions DB (rw) |

`travel.py` derives `SKILL_DIR` from its own path, so it **must** live at
`/app/travel/travel-agent/scripts/travel.py` — mounting it at `/app/web/` breaks every
sibling script lookup. SearXNG is reached through `SEARXNG_URL` from `.env` (basic auth),
not `127.0.0.1:8080`.

## Tools Available

| Tool | Source |
|---|---|
| Flight prices | Travelpayouts |
| Flight status | AviationStack + AirLabs |
| Airport info / routes | AirLabs |
| YVR deals | yvrdeals.com |
| Hotels | Web + Google Places |
| Travel advisories | Gov of Canada |
| Weather | Open-Meteo |
| Currency | Exchange rates |
| Translation | LibreTranslate (self-hosted) |
| Web search | SearXNG (self-hosted) |
