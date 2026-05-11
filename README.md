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
# Route: travel.ogsapps.cc → localhost:8091
```

## Architecture

```
Browser → CF Tunnel → :8091 → FastAPI → Pi (Z.AI) → travel.py CLI → APIs
```

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
