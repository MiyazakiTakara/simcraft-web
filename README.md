# SimCraft Web

> 🇵🇱 [Polska wersja README](./README.pl.md)

A web-based DPS simulator for World of Warcraft powered by SimulationCraft.

> The application is **DPS-only** — healer and tank simulations are not supported.

## Features

- **Battle.net Login** — OAuth2 authorization, character fetching from armory
- **Armory Simulations** — automatic character data retrieval from Blizzard API
- **Addon Export Simulations** — paste SimulationCraft addon text without logging in
- **Simulation History** — all simulations saved; public list of recent results with pagination
- **DPS Charts** — Total DMG + DPS pie charts (Plotly/kaleido, rendered server-side to PNG)
- **Social Sharing** — every result has a unique URL with OG meta tags (Discord, Twitter previews)
- **Admin Panel** — manage news, simulation limits, health check, active job list (Keycloak OAuth2)
- **Rate Limiting** — API abuse protection (slowapi, per-IP)
- **Watchdog** — automatic cleanup of old jobs and timeout handling
- **Internationalization** — full i18n PL/EN with language switcher, browser auto-detection and `localStorage` persistence
- **Main Character** — modal on first login to select main character; saved to session; displayed in header

## TODO

### Navigation

- [ ] **Persist view on refresh** — on page reload the user should return to the same view (home/simulations/profile). Currently always resets to `home`. Proposed solution: save active tab in `localStorage` or URL hash (`#symulacje`) and read it in `init()`.

### Simulation History

- [ ] **Hide guest simulation results from public history** — simulations run without logging in (addon export on the home page) should not appear in the public history list anywhere. The result should still be accessible via a direct link `/result/{job_id}` (e.g. to share with friends). Required changes:
  - Backend: add an `is_guest: bool` flag when saving to history (or use `user_id IS NULL` as the indicator); `GET /api/history` endpoint should filter out entries where `is_guest = true`
  - Frontend: `startGuestSim()` in `sim.js` should either not call `API.saveToHistory()` at all, or pass the guest flag — TBD

### Social Features

> **User identity problem:** Users log in via Battle.net OAuth and own multiple characters. Planned approach: on first login the user picks a **main character**, which becomes their public profile. All simulations are still tied to the account (session UUID), but the public display name is in the format `Name-Realm`.

- [x] **Main character selection** — modal on first login or in settings; saved to new `main_character` column in sessions table
- [ ] **User profiles** — `/u/{realm}/{name}` page with simulation history, selected main character as profile avatar
- [ ] **Rankings** — TOP DPS table per class/spec/fight style, generated from public history
- [ ] **Comments / reactions** — emoji reactions or short comment under a simulation result (per `job_id`)
- [ ] **Build sharing** — export simulation config (addon text + parameters) as a public link to re-run
- [ ] **Simulation comparison** — `/compare?a={job_id}&b={job_id}` view with spell diff and side-by-side DPS
- [ ] **Trend tracking** — DPS over time chart for a specific character (endpoint `/api/history/trend` already exists, UI missing)

### Internationalization

- [x] **i18n frontend** — UI strings extracted to `locales/pl.json` and `locales/en.json`; Alpine.js `$store.i18n` handles reactive language switching
- [x] **Automatic language detection** — based on `navigator.language` or setting saved in `localStorage`
- [x] **English as default** — English is the default language; PL/EN switcher visible in the header on every page
- [x] **Spell name localization** — spell names remain in English (SimulationCraft + WoW use EN; players are used to it)

### Technical

- [x] **Race condition in `simulation.py`** — `out_path` passed as argument to `_run_sim()`, not read from `jobs[]` outside the lock
- [x] **Alpine.js getters in mixins** — `sortedSpells`, `filteredChars`, `pagedHistory`, `pagedNews` etc. must be defined via `Object.defineProperties` (through `mergeMixins`), not `...spread` — spread destroys getter descriptors
- [x] **Pin versions in `requirements.txt`** — all 13 dependencies already use exact `==` version pinning; verified and closed via PR #11
- [ ] **CSV result export** — `GET /api/result/{job_id}/csv` endpoint returning spell breakdown (makes sense after build comparison is added)

## Requirements

- Python 3.10+
- PostgreSQL
- Docker & Docker Compose (recommended)
- Battle.net developer account (OAuth2)
- Keycloak (for admin panel)

## Local Setup

### Docker Compose

```bash
cp .env.example .env
# edit .env and fill in environment variables

docker compose up --build
```

### Manual

```bash
# Build SimulationCraft
git clone --depth=1 https://github.com/simulationcraft/simc.git
cd simc
cmake -DBUILD_GUI=OFF -DCMAKE_BUILD_TYPE=Release -S . -B build
cmake --build build --parallel $(nproc)
cp build/simc /app/SimulationCraft/simc

# Backend
pip install -r requirements.txt
export BLIZZARD_CLIENT_ID=...
export BLIZZARD_CLIENT_SECRET=...
export DATABASE_URL=postgresql://simcraft:simcraft@localhost:5432/simcraft
# ... other environment variables (see .env.example)

cd backend
uvicorn main:app --reload
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|----------|
| `BLIZZARD_CLIENT_ID` | Battle.net OAuth app ID | — |
| `BLIZZARD_CLIENT_SECRET` | Battle.net OAuth app secret | — |
| `REDIRECT_URI` | OAuth callback URL after Battle.net auth | — |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://simcraft:simcraft@db:5432/simcraft` |
| `KEYCLOAK_URL` | Keycloak URL (for admin panel) | — |
| `KEYCLOAK_REALM` | Keycloak realm | — |
| `KEYCLOAK_CLIENT_ID` | Keycloak client ID | — |
| `KEYCLOAK_CLIENT_SECRET` | Keycloak client secret | — |
| `ADMIN_REDIRECT_URI` | OAuth callback URL after admin login | — |
| `BASE_URL` | Base application URL (used in OG meta tags) | `https://sim.miyazakitakara.ovh` |
| `RESULTS_DIR` | Directory for simulation results | `/app/results` |
| `SIMC_PATH` | Path to simc binary | `/app/SimulationCraft/simc` |
| `MAX_CONCURRENT_SIMS` | Max number of concurrent simulations | `3` |
| `JOB_TIMEOUT` | Simulation timeout in seconds | `360` |
| `JOBS_TTL` | Lifetime of completed jobs in memory (seconds) | `14400` (4h) |
| `LOG_LEVEL` | Log level | `INFO` |

## Project Structure

```
simcraft-web/
├── backend/
│   ├── main.py            # FastAPI app, routing, OG meta, startup
│   ├── auth.py            # Battle.net OAuth2
│   ├── characters.py      # Blizzard character API (list, media, equipment, stats, talents)
│   ├── simulation.py      # simc runner, job queue, watchdog
│   ├── results.py         # JSON result parsing, PNG chart generation
│   ├── history.py         # Simulation history, trends, metadata
│   ├── database.py        # SQLAlchemy models, inline migrations
│   ├── admin.py           # Admin panel (Keycloak), news, logs, limits
│   └── logging_config.py  # Structured logging (structlog)
├── frontend/
│   ├── index.html         # Main page
│   ├── result.html        # Result page (OG meta, spell breakdown, chart)
│   ├── admin.html         # Admin panel
│   ├── app.js             # Alpine.js logic (main page); view router (loadView/navigateTo)
│   ├── sim.js             # Simulation form logic (SimMixin)
│   ├── chars.js           # Character list, equipment, talents (CharsMixin)
│   ├── history.js         # History widget (HistoryMixin)
│   ├── api.js             # API client (fetch wrapper)
│   ├── utils.js           # Helpers (number formatting, class colors, etc.)
│   ├── admin.js           # Admin panel logic
│   ├── i18n.js            # Translation system (Alpine store, auto-detect, localStorage)
│   ├── style.css          # Styles (dark theme)
│   ├── views/
│   │   ├── home.html        # Home view (hero, addon form, public history, news)
│   │   ├── symulacje.html   # Simulations view (character list, form, results, history)
│   │   └── profil.html      # User profile view
│   └── locales/
│       ├── pl.json          # Polish translations
│       └── en.json          # English translations
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## Frontend Architecture

The frontend uses **Alpine.js** with a mixin pattern. Key rules:

- `app()` is the only Alpine `x-data` on the main page
- Views (`views/*.html`) are loaded dynamically by `loadView(name)` into `#view-container` and initialized via `Alpine.initTree()` — **they have no own `x-data`**, they operate within the parent scope
- Mixins (`SimMixin`, `CharsMixin`, `HistoryMixin`) are merged by `mergeMixins()` which uses `Object.defineProperties` — this ensures getters (e.g. `sortedSpells`, `filteredChars`) are correctly copied with their descriptors preserved
- Getters that reference `this.*` must be defined directly in the `state` object in `app()`, not in mixins — `...spread` destroys getter descriptors

## API

### Simulation
- `POST /api/simulate` — run a simulation
- `GET /api/job/{job_id}` — job status (`running` / `done` / `error`)
- `GET /api/result/{job_id}/json` — results in JSON format
- `GET /api/result/{job_id}/dps-chart.png` — DPS chart as PNG
- `GET /api/result/{job_id}/meta` — simulation metadata (character, class, fight style)

### History
- `GET /api/history` — public history (pagination: `?page=1&limit=50`); excludes guest simulations
- `GET /api/history/mine` — logged-in user's history
- `GET /api/history/trend` — DPS over time for a specific character

### Characters
- `GET /api/characters` — account character list (requires session)
- `GET /api/character-media` — character avatar
- `GET /api/character/equipment` — character equipment
- `GET /api/character/statistics` — character statistics
- `GET /api/character/talents` — character talents

### Auth
- `GET /auth/login` — redirect to Battle.net OAuth
- `GET /auth/callback` — OAuth callback
- `GET /auth/logout` — logout
- `GET /auth/session/info` — session info (main character, is_first_login)
- `PATCH /auth/session/main-character` — set main character
- `POST /auth/session/skip-first-login` — skip main character selection modal

### Admin
- `GET /admin` — admin panel (requires Keycloak session)
- `GET /admin/api/limits` — get system limits
- `PATCH /admin/api/limits` — update system limits
- `GET /admin/api/health` — service health check
- `GET /admin/api/tasks` — list active jobs
- `DELETE /admin/api/tasks/{job_id}` — cancel a job

## License

MIT
