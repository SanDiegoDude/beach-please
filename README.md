# Beach, Please

> A sassy AI beach concierge that aggregates waves, rip currents, NWS alerts,
> tides, water quality, sharks, and amenities for any US beach — so you can
> stop opening seven apps before you put on sunscreen.

```
        🌊      🌊       🌊
   ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
   .   Beach,                        .   .
       Please.       (sass included)
   .   .   .   .   .   .   .   .   .   .
```

Originally built for a vibe-code club demo. Now wired up to live as a real
self-hosted home service so my family can ask "is the water gross at Imperial
Beach this weekend?" from any phone on the Wi-Fi and get a real answer.

---

## What it does

A single chat box. Ask it anything beach-shaped about a US beach. It fans out
to NOAA, Open-Meteo, OpenStreetMap, and state-level water quality feeds,
then writes a sassy, safety-aware answer with attitude.

Examples:

- "Is Imperial Beach safe this weekend? I heard about Tijuana sewage."
- "Find me the safest beach near LA for a 3-year-old this Saturday morning."
- "Compare Pismo and Cocoa Beach FL for tomorrow morning."
- "Should I surf Pipeline this week or am I going to die?"

You'll see each tool the agent calls flash by in real time (lookup_beach,
get_waves, get_water_quality, …) before the markdown answer streams in.

## Data sources (all free, no scraping, no keys)

| Signal             | Source                                                  |
| ------------------ | ------------------------------------------------------- |
| Beach lookup       | Curated catalog → falls back to OpenStreetMap Nominatim |
| Waves & swell      | Open-Meteo Marine (`ncep_gfswave025`)                   |
| Rip current risk   | NOAA NWS Surf Zone Forecast (parsed by zone)            |
| Active warnings    | NOAA NWS `/alerts/active?point=lat,lon`                 |
| Tides + water temp | NOAA CO-OPS (pre-mapped, or nearest station resolved live) |
| Water quality      | SD County DEH (sdbeachinfo.com — Tijuana sewage closures) + FL DOH Healthy Beaches; graceful fallback elsewhere |
| Shark history      | Bundled GSAF-derived CSV, queried by radius             |
| Amenities          | OpenStreetMap Overpass (toilets, parking, showers, ...) |

The catalog ships ~16 beaches across CA, FL, HI, NC, SC, NY, NJ, OR, WA, TX
to seed the UI's "featured" tiles, but **any US beach name works** —
`lookup_beach` falls through to live OpenStreetMap geocoding, the runtime-
geocoded beach gets its nearest CO-OPS tide station resolved on the fly, and
every other tool fans out from lat/lon. Nothing is canned.

---

## Quick start

You'll need:

- Python 3.11+
- Node 20+
- An OpenAI key **OR** a running local LM Studio / Ollama

The application itself is pure Python + Node — fully cross-platform. Pick
your OS for the wrapper scripts:

### macOS / Linux

```bash
git clone <this-repo> beach-please
cd beach-please
make install              # one-shot: venv, deps, env files
$EDITOR backend/.env      # paste OpenAI key or LM Studio URL
make dev                  # starts both backend and frontend
```

`make install` is idempotent and uses [`uv`](https://docs.astral.sh/uv/) if
present (~10x faster) or falls back to plain `pip + venv`.

### Windows (PowerShell)

```powershell
git clone <this-repo> beach-please
cd beach-please
.\scripts\windows\install.ps1     # venv, deps, env files
notepad backend\.env              # paste OpenAI key or LM Studio URL
.\scripts\windows\dev.ps1         # starts both backend and frontend
```

If you get an execution-policy error on the first run:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

This is per-user and doesn't need admin.

### Open it

Open http://localhost:5757 and start asking.

| Process  | Port | URL                           |
| -------- | ---- | ----------------------------- |
| Backend  | 8765 | http://localhost:8765/api     |
| Frontend | 5757 | http://localhost:5757         |

Logs live at `logs/backend.log` and `logs/frontend.log`. Stop everything
with `make stop` / `.\scripts\windows\stop.ps1` (or Ctrl-C from the dev
runner).

---

## Run it on the home Wi-Fi (real family use)

Pick the always-on machine on your network (a spare Mac mini, a Linux box,
the Windows machine where LM Studio already lives — whatever). Install
once, then access from any phone, tablet, or laptop on the Wi-Fi.

### Install as a service (auto-starts on boot, restarts on crash)

| OS      | Command                                       | Mechanism             |
| ------- | --------------------------------------------- | --------------------- |
| macOS   | `make install-service`                        | launchd user agent    |
| Linux   | `make install-service`                        | systemd user service  |
| Windows | `.\scripts\windows\install-task.ps1`          | Task Scheduler        |

All three:

- Start automatically when you log in.
- Restart automatically on crash.
- Bind the backend to `0.0.0.0:8765` so other devices on the LAN can reach it.
- Build and run the frontend in production mode (`next start`).
- Log to `logs/backend.log` and `logs/frontend.log`.

Uninstall: `make uninstall-service` (Mac/Linux) or
`.\scripts\windows\uninstall-task.ps1` (Windows).

### Headless / SSH-only Linux servers

systemd user services normally pause when you log out. To keep them
running 24/7 on a headless box, run **once** as root:

```bash
sudo loginctl enable-linger $USER
```

That tells systemd to keep your user manager alive across logins.

### Headless / SSH-only Windows servers

Task Scheduler tasks installed by the script run in your interactive user
session, so they pause if you log out. For true 24/7 headless behavior on
Windows, the cleanest option is [NSSM](https://nssm.cc/) ("the Non-Sucking
Service Manager") — it wraps a command into a real Windows service:

```powershell
nssm install BeachPleaseBackend  C:\path\to\beach-please\backend\.venv\Scripts\uvicorn.exe
nssm set     BeachPleaseBackend  AppDirectory  C:\path\to\beach-please\backend
nssm set     BeachPleaseBackend  AppParameters app.main:app --host 0.0.0.0 --port 8765
nssm install BeachPleaseFrontend C:\Program Files\nodejs\npm.cmd
nssm set     BeachPleaseFrontend AppDirectory  C:\path\to\beach-please\frontend
nssm set     BeachPleaseFrontend AppParameters run start
```

Then `Start-Service BeachPleaseBackend; Start-Service BeachPleaseFrontend`.

### Get the host's LAN IP

| OS      | Command                                                   |
| ------- | --------------------------------------------------------- |
| macOS   | `ipconfig getifaddr en0`                                  |
| Linux   | `hostname -I` or `ip -4 route get 1.1.1.1`                |
| Windows | `(Get-NetIPAddress -AddressFamily IPv4).IPAddress`        |

### From any phone or tablet on the Wi-Fi

Open `http://<host-LAN-IP>:5757` in Safari or Chrome. That's it.

The frontend auto-detects the backend on the same hostname, so no
per-device setup is needed. Bookmark it. Add it to your home screen if you
want a fake-app icon.

### Firewall

You may need to allow inbound traffic on ports 5757 and 8765:

- **macOS**: System Settings → Network → Firewall → Options → allow
  `python3` (or `uvicorn`) and `node`. The first time you start it, you
  should see a permission dialog.
- **Linux (UFW)**: `sudo ufw allow 5757/tcp && sudo ufw allow 8765/tcp`
- **Windows**: `New-NetFirewallRule -DisplayName "Beach Please" -Direction Inbound -LocalPort 5757,8765 -Protocol TCP -Action Allow`
  (run elevated)

### Optional: run the AI provider locally too

Point `OPENAI_BASE_URL` at LM Studio or Ollama on the same machine (or
another box on the LAN — e.g. `http://192.168.1.42:1234/v1`).
See the AI provider section below. This way the whole thing works offline
— useful when the WAN is down and the toddler wants to know if there's
seaweed.

---

## AI provider — bring your own (the double bonus)

Beach, Please uses the OpenAI Python SDK with a configurable `base_url`. So
it works against:

- OpenAI (`api.openai.com`)
- LM Studio (`localhost:1234` or any host on your LAN)
- Ollama (`localhost:11434`)
- Any OpenAI-compatible endpoint with tool-calling support

Three profiles ship in `backend/.env.example`. To swap providers, edit two
lines in `backend/.env` and restart. The agent code never changes.

### Models known to work

| Provider  | Model                                            | Notes                       |
| --------- | ------------------------------------------------ | --------------------------- |
| OpenAI    | `gpt-4o-mini`                                    | Default, fast, cheap        |
| OpenAI    | `gpt-4o`                                         | Best answers                |
| LM Studio | `qwen3.5-4b`                                     | Fast on M-series Mac (~25s) |
| LM Studio | `qwen2.5-7b-instruct`                            | Recommended local sweet spot |
| LM Studio | `qwen3.6-35b-a3b-uncensored-hauhaucs-aggressive` | Best local answers, slower   |
| Ollama    | `qwen2.5:7b` / `llama3.1:8b`                     | Solid all-rounders          |

Avoid `gpt-oss-*` via LM Studio for now — it emits raw template tokens
through the OpenAI-compatible endpoint instead of structured tool calls.

### Local LLM template quirk (already worked around)

Some local templates (Qwen variants on LM Studio) reject the OpenAI `tool`
role. The backend setting `tool_results_as_user=true` (default) folds tool
results into a synthetic user message so any OpenAI-compatible model with
tool-calling works. If you're on a hosted OpenAI endpoint and want strict
spec compliance, set `TOOL_RESULTS_AS_USER=false` in `backend/.env`.

---

## How the agent works

```
User question
   ↓
FastAPI POST /api/chat (SSE stream out)
   ↓
agent.run_chat()
   ├─ system prompt: Beach, Please persona
   ├─ tools: 9 OpenAI-compatible function schemas
   └─ loop (≤10 iterations):
       ├─ chat.completions.create(tools=...)
       ├─ if tool_calls: dispatch in parallel via asyncio.gather
       │                 emit tool_call + tool_result events
       └─ else: stream final response tokens
```

Each tool is a plain `async def` that returns JSON. A small in-memory TTL
cache (10 min) sits in front of every tool, so repeated questions stay
snappy and we stay polite to the upstream APIs.

The frontend keeps the last 2 user/assistant turns and trims older history
before sending — so prompts stay short and the model knows to ask for
clarification if you reference something further back.

---

## Make targets (macOS / Linux)

```
make install            One-shot setup (Python venv, deps, env files)
make dev                Start backend + frontend together
make stop               Stop everything
make backend            Start backend only (foreground, with --reload)
make frontend           Start frontend only (foreground)
make logs               Tail backend + frontend logs
make clean              Wipe .venv, node_modules, .next, logs

make install-service    Install always-on service (launchd on Mac, systemd on Linux)
make uninstall-service  Remove the service
```

Windows users skip `make` entirely and call the PowerShell scripts:
`install.ps1`, `dev.ps1`, `stop.ps1`, `install-task.ps1`, `uninstall-task.ps1`.

## Repo layout

```
beach-please/
├── Makefile                     # mac/linux task runner (install, dev, ...)
├── README.md
├── LICENSE                      # MIT
├── .env.example                 # canonical env template
├── .gitignore
│
├── scripts/
│   ├── install.sh               # mac/linux: idempotent setup
│   ├── dev.sh                   # mac/linux: run both, live logs, cleanup
│   ├── stop.sh                  # mac/linux: kill both
│   ├── macos/
│   │   ├── install-launchd.sh
│   │   ├── uninstall-launchd.sh
│   │   └── com.beachplease.{backend,frontend}.plist.tmpl
│   ├── linux/
│   │   ├── install-systemd.sh
│   │   ├── uninstall-systemd.sh
│   │   └── beach-please-{backend,frontend}.service.tmpl
│   └── windows/
│       ├── install.ps1
│       ├── dev.ps1
│       ├── stop.ps1
│       ├── install-task.ps1     # Task Scheduler always-on
│       └── uninstall-task.ps1
│
├── backend/                     # FastAPI + agent (Python, cross-platform)
│   ├── pyproject.toml           # uv-friendly
│   ├── requirements.txt         # pip-friendly mirror
│   ├── .env.example
│   └── app/
│       ├── main.py
│       ├── agent.py             # the LLM loop
│       ├── personality.py       # system prompt (single source of truth)
│       ├── catalog.py           # static + dynamic beach catalog
│       ├── geocoding.py         # OSM Nominatim live lookup
│       ├── cache.py             # in-memory TTL cache
│       ├── http.py              # shared httpx client
│       ├── routes/              # /api/beaches, /api/chat
│       ├── tools/               # one file per tool (waves, tides, ...)
│       └── data/                # beaches.json, gsaf_sharks.csv
│
└── frontend/                    # Next.js 15 + Tailwind 4 (cross-platform)
    ├── package.json
    ├── .env.example
    ├── app/                     # App Router
    ├── components/
    │   ├── AgentChat.tsx        # the chat surface
    │   └── ChatPage.tsx
    └── lib/                     # api.ts, types.ts
```

---

## Honest limitations

- US beaches only. NOAA APIs don't cover anywhere else.
- Catalog is curated, not exhaustive. Add what you need to
  `backend/app/data/beaches.json` — or just type the beach name into the
  chat and let live geocoding handle it.
- Water quality coverage is fragmented in real life. We hit FL DOH directly,
  and SD County DEH (sdbeachinfo.com) for the San Diego coast — that's the
  one that catches Tijuana sewage closures at Imperial Beach / Border Field
  in real time. Other CA beaches link out to Heal the Bay; everywhere else
  links out to EPA BEACON. PRs to wire up more state feeds welcome.
- Shark dataset is a curated GSAF subset, not the full archive. Drop a
  fuller GSAF CSV at `backend/app/data/gsaf_sharks.csv` and richer counts
  appear automatically.
- This is a hobby project. Always check posted signs and lifeguards before
  entering the water.

---

## Demo script (10 min, for the vibe-code club)

1. **(1 min) Set up.** "My wife wants to go to the beach for Mother's Day.
   She named the problem. I named the app."
2. **(2 min) Click a featured beach.** Watch tool calls flash across the
   chat in real time as the agent fans out to ~5 APIs in parallel.
3. **(2 min) Live geocode the long tail.** "Should I surf Pismo Beach this
   weekend?" Pismo isn't in the curated catalog — `lookup_beach` geocodes
   it via OpenStreetMap, the nearest CO-OPS station gets resolved live, and
   every other tool fans out against the new lat/lon.
4. **(2 min) The Tijuana sewage flex.** "Is Imperial Beach safe this
   weekend?" The agent pulls a real closure from sdbeachinfo.com and leads
   with the safety warning.
5. **(2 min) The double bonus.** Show that the AI provider is just
   `OPENAI_BASE_URL` — point at LM Studio, restart, re-run the question.
   Same app, fully local, mic drop.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| "No user message in request" | Stale chat state from a prior failed turn | Hard-refresh; the new client filters empty turns out of history |
| Frontend won't load on phone | Backend bound to 127.0.0.1 instead of 0.0.0.0, or firewall blocking | The supplied dev/service scripts bind 0.0.0.0; also open ports 5757 and 8765 in your OS firewall (see "Firewall" above) |
| LM Studio "No user query found in messages" | Model template chokes on OpenAI `tool` role | `tool_results_as_user=true` is the default in `backend/.env` — it works around this. If you disabled it, re-enable. |
| Streaming response never appears in UI | Next.js dev proxy buffering SSE | Already handled — client hits the backend directly via `resolveStreamBase()` |
| `Cannot find module './611.js'` after `next build` | Build artifacts collided with dev cache | `rm -rf frontend/.next && make dev` (or `Remove-Item -Recurse -Force frontend\.next` on Windows) |
| Stale uvicorn process holding port 8765 | Previous process didn't clean up | `make stop` / `.\scripts\windows\stop.ps1` |
| Windows: "running scripts is disabled on this system" | PS execution policy | Run once: `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` (per-user, no admin) |
| Windows: ports 5757/8765 not reachable from phone | Windows Defender Firewall blocking | Add inbound rule (see "Firewall" above) or temporarily disable to confirm |
| Linux: service stops when I SSH out | systemd user services need linger to outlive your session | `sudo loginctl enable-linger $USER` once |

---

Built in one weekend. Beach, please.
