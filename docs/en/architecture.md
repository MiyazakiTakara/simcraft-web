# SimCraft Web — Architecture

The application runs as a set of Docker containers managed by Docker Compose.

## Tech Stack

| Layer | Technology | Notes |
|-------|------------|-------|
| Backend API | FastAPI (Python 3.11) | async, Pydantic v2 |
| Frontend | Alpine.js + Vanilla JS | MPA (Multi-Page App) |
| Database | PostgreSQL 15 | SQLAlchemy ORM |
| Reverse proxy | nginx | TLS termination, static files |
| Auth | Keycloak (OIDC) | OAuth2 + session cookie |
| Simulator | SimulationCraft (`simc`) | binary, branch `midnight` |
| Cache | In-memory (Python dict) | simc version, appearance config |

## Containers (docker-compose.yml)

- **app** — FastAPI on internal port `8000`; mounts `/app/frontend`, `/app/results`, `/app/config`
- **db** — PostgreSQL 15, volume `pgdata`, internal port `5432`
- **nginx** — reverse proxy, ports `80`/`443`, serves static files directly, TLS termination (certbot/Let's Encrypt)
- **keycloak** — OIDC provider on internal port `8080`; used for user and admin login

## Directory Structure

```
simcraft-web/
├── backend/          # FastAPI app
│   ├── main.py         # Entry point, router registration, page routes
│   ├── admin.py        # Admin panel backend + auth
│   ├── admin_docs.py   # Docs browser endpoints
│   ├── simulation.py   # Job queue + simc subprocess
│   ├── results.py      # Result data endpoints + meta
│   ├── history.py      # User simulation history
│   ├── rankings.py     # Global DPS rankings
│   ├── reactions.py    # Emoji reactions
│   ├── characters.py   # Character/armory data
│   ├── profiles.py     # User profiles
│   ├── favorites.py    # Saved favorites
│   ├── icons.py        # Item/spell icon proxy
│   ├── auth.py         # Blizzard OAuth + Keycloak helpers
│   ├── database.py     # SQLAlchemy models + SessionLocal
│   ├── simc_parser.py  # simc JSON output parser
│   └── traffic.py      # TrafficMiddleware (page visit tracking)
├── frontend/         # Static HTML/JS/CSS
│   ├── admin.html      # Admin panel (mini-SPA)
│   ├── admin/          # Admin panel JS modules
│   ├── result.html     # Simulation result page
│   ├── result-panel.html # Result component (injected by backend)
│   ├── rankings.html   # Rankings
│   ├── profile.html    # User profile /u/:bnetId
│   ├── profil-page.html # /profil (logged-in user)
│   ├── sim.html        # Simulation form
│   ├── locales/        # i18n (pl.json, en.json)
│   └── static/         # Images, icons
├── docs/             # This documentation
│   ├── pl/             # Polish docs
│   └── en/             # English docs
├── config/           # appearance.json (generated at runtime)
├── nginx/            # nginx.conf
└── docker-compose.yml
```

## Simulation Flow

```
User → nginx → FastAPI POST /api/simulate
  → validate simc_input (regex, max length)
  → check rate limit (5 req/min per user)
  → check MAX_CONCURRENT_SIMS
  → save JobModel (status: queued) to PostgreSQL
  → asyncio task started in background
      → subprocess: simc input_file.simc json_file=output.json
      → parse outputs via simc_parser.py
      → save results to /app/results/{job_id}.json
      → save to HistoryEntryModel (DPS, class, spec, realm...)
      → update JobModel (status: done)
  → GET /api/result/{job_id}/status → polling every 2s
  → GET /api/result/{job_id}/meta   → metadata + OG tags
  → GET /api/result/{job_id}/json   → full result data
```

## Database Models

| Model | Table | Description |
|-------|-------|-------------|
| `JobModel` | `jobs` | Simulation task status |
| `HistoryEntryModel` | `history` | Simulation results with metadata |
| `NewsModel` | `news` | News items published on the site |
| `LogEntryModel` | `logs` | Application logs |
| `AdminSessionModel` | `admin_sessions` | Admin sessions |
| `PageVisitModel` | `page_visits` | Traffic tracking |
| `ReactionModel` | `reactions` | Emoji reactions on results |
| `FavoriteModel` | `favorites` | Saved favorite simulations |

## Configuration Files

- `config/appearance.json` — UI customization (title, emoji, hero text); created automatically on first start
- `.env` — environment variables (DB_URL, Keycloak, Blizzard API keys, paths)
- `nginx/nginx.conf` — nginx configuration (proxy_pass, TLS, static files, gzip)

## Architecture Notes

- The frontend is an **MPA** (not SPA) — each subpage is a separate HTML file served by FastAPI or nginx
- `result.html` and `sim.html` are **server-side rendered** — the backend injects `result-panel.html` and OG meta tags before returning the page
- The admin panel is an **exception** — it works as a mini-SPA with its own tab router
- No Redux/Vuex/Pinia — state is managed in Alpine.js `$store` or module-level JS variables
