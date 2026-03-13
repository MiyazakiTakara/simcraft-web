# SimCraft Web

> 🇵🇱 [Polska wersja README](./README.pl.md)

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![Alpine.js](https://img.shields.io/badge/Alpine.js-3.x-8BC0D0?logo=alpine.js&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)

A web-based DPS simulator for World of Warcraft powered by SimulationCraft.

> The application is **DPS-only** — healer and tank simulations are not supported.

## Screenshots

<!-- Add screenshots here -->

## Features

- **Battle.net Login** — OAuth2 authorization, character fetching from armory
- **Armory Simulations** — automatic character data retrieval from Blizzard API
- **Addon Export Simulations** — paste SimulationCraft addon text without logging in
- **Simulation History** — all simulations saved, tied to Battle.net account (persists across browsers and re-logins); public list of recent results with pagination
- **DPS Trend Chart** — DPS over time chart per character and fight style in the profile view
- **Emoji Reactions** — 🔥💪😢💀🤣 reactions on simulation results; toggle/swap like YouTube thumbs; logged-in users only
- **DPS Charts** — Total DMG + DPS pie charts (Plotly/kaleido, rendered server-side to PNG)
- **CSV Export** — download spell breakdown as CSV from any result page
- **Social Sharing** — every result has a unique URL with OG meta tags (Discord, Twitter previews)
- **Rankings** — `/rankings` page with TOP DPS podium (🥇🥈🥉) + table for places 4–10; filterable by fight style, class, spec; one entry per unique character; top 3 mini-podium on home page
- **Admin Panel** — manage news, appearance, simulation limits, health check, active job list (Keycloak OAuth2)
- **Rate Limiting** — API abuse protection (slowapi, per-IP)
- **Watchdog** — automatic cleanup of old jobs and timeout handling
- **Internationalization** — full i18n PL/EN with language switcher, browser auto-detection and `localStorage` persistence
- **Main Character** — modal on first login to select main character; saved permanently to Battle.net account (`users` table); displayed in header dropdown
- **User Dropdown Menu** — header dropdown under the main character name with: Characters, History, Public Profile, Favorites, Settings, Logout
- **View Persistence** — active view (home/symulacje/profil/ustawienia/ulubione) persisted via URL hash; browser back/forward works correctly
- **Settings Page** — change main character (select from character list), language preference, theme preference; profile privacy toggle; per-character privacy
- **Sliding Session** — session TTL extended by 30 days on every active use; no forced re-logins during normal usage
- **Skeleton Loaders** — loading skeletons on home, symulacje, profil views instead of spinners
- **Smart History Loading** — home always loads public history; `/symulacje` and `/profil` load private history for logged-in users, public for guests; history reloads on every view switch
- **Design Tokens** — CSS custom properties for all colors (including `--danger` with dark/light theme variants), spacing, typography, radius, shadows
- **Public Profiles** — every Battle.net user has a public profile at `/u/{bnet_id}` showing main character, best DPS, sim count and history; respects privacy settings
- **Favorites** — logged-in users can favorite any public profile (❤️ button on profile page); favorites are tied to `bnet_id` and persist across all devices; accessible via `/#ulubione`

## Roadmap

### 🔜 Planned
- [ ] **Build sharing** — export simulation config as a public link to re-run
- [ ] **Simulation comparison** — `/compare?a={job_id}&b={job_id}` with spell diff and side-by-side DPS
- [ ] **Custom SVG icons (Arcane style)** — replace emoji and placeholder images with custom SVG assets: class icons, default character avatars, item slot icons, UI elements; cartoon style inspired by Arcane anime
- [ ] **Result page enhancements** — spell icons from WoW CDN, action sequence timeline, buff uptime bars

### ✅ Done (2026-03-13)
- [x] **Public profiles + Favorites** — `/u/{bnet_id}` public profile pages; ❤️ favorites system with `favorites` table; `/#ulubione` view in SPA; counter shown on profile; Alpine race condition fix (`favoritesView` extracted to `favorites.js`) ([#35](https://github.com/MiyazakiTakara/simcraft-web/issues/35))
- [x] **Settings: remove manual character entry** — removed manual name/realm text inputs from settings view; only dropdown select from character list remains ([#28](https://github.com/MiyazakiTakara/simcraft-web/issues/28))
- [x] **Design token `--danger`** — added `--danger` CSS variable (`#c0392b` dark / `#e74c3c` light) to `:root` and `[data-theme="light"]`; `.btn-danger` and `.seg-btn.active` now use `var(--danger)` instead of hardcoded hex

### ✅ Done (2026-03-12)
- [x] **Settings: character picker** — replace manual name/realm text inputs with character list (same as simulation tab); user clicks to select, no typing
- [x] **Settings: per-character privacy** — in addition to global account privacy toggle, allow hiding/showing individual characters from public profile
- [x] **Rankings: exclude addon simulations** — filter out results submitted via the WoW addon (`source=addon` flag); only web simulations should appear in rankings
- [x] **Skeleton loaders: profil.html** — char cards grid and history section
- [x] **Skeleton loaders: home.html + symulacje.html** — public history grid, top 3 podium, history sidebar ([#27](https://github.com/MiyazakiTakara/simcraft-web/issues/27))
- [x] **Smart history loading** — `navigateTo()` switches between public/private history per view; `historyLoading` → `loadingHistory` ReferenceError fixed ([#33](https://github.com/MiyazakiTakara/simcraft-web/issues/33))
- [x] **Fix `/rankings` 404** — added explicit FastAPI route; `StaticFiles(html=True)` does not auto-map `/foo` → `foo.html` ([#32](https://github.com/MiyazakiTakara/simcraft-web/issues/32))
- [x] **Auto build version** — Dockerfile now auto-generates version tag from git hash to prevent browser cache issues
- [x] **Fix `/result/{job_id}` 404** — added explicit route to serve result.html ([#34](https://github.com/MiyazakiTakara/simcraft-web/issues/34))
- [x] **Fix result page data loading** — added missing `/api/result/{job_id}/meta` endpoint for character info

## Requirements

- Python 3.10+
- PostgreSQL 15+
- Docker & Docker Compose (recommended)
- Battle.net developer account (OAuth2 app)
- Keycloak (for admin panel)

## Local Setup

### Docker Compose (recommended)

```bash
cp .env.example .env
# Edit .env and fill in all required environment variables

docker compose up --build
```

The app will be available at `http://localhost:8000`.

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

cd backend
uvicorn main:app --reload
```

## Environment Variables

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `BLIZZARD_CLIENT_ID` | ✅ | Battle.net OAuth app ID | — |
| `BLIZZARD_CLIENT_SECRET` | ✅ | Battle.net OAuth app secret | — |
| `REDIRECT_URI` | ✅ | OAuth callback URL after Battle.net auth | — |
| `DATABASE_URL` | ✅ | PostgreSQL connection string | `postgresql://simcraft:simcraft@db:5432/simcraft` |
| `BASE_URL` | ✅ | Base application URL (used in OG meta tags and share links) | `https://sim.miyazakitakara.ovh` |
| `KEYCLOAK_URL` | ⚠️ admin | Keycloak URL (for admin panel) | — |
| `KEYCLOAK_REALM` | ⚠️ admin | Keycloak realm | — |
| `KEYCLOAK_CLIENT_ID` | ⚠️ admin | Keycloak client ID | — |
| `KEYCLOAK_CLIENT_SECRET` | ⚠️ admin | Keycloak client secret | — |
| `ADMIN_REDIRECT_URI` | ⚠️ admin | OAuth callback URL after admin login | — |
| `RESULTS_DIR` | | Directory for simulation results | `/app/results` |
| `SIMC_PATH` | | Path to simc binary | `/app/SimulationCraft/simc` |
| `MAX_CONCURRENT_SIMS` | | Max number of concurrent simulations | `3` |
| `JOB_TIMEOUT` | | Simulation timeout in seconds | `360` |
| `JOBS_TTL` | | Lifetime of completed jobs in memory (seconds) | `14400` (4h) |
| `ALLOWED_ORIGINS` | | CORS allowed origins (comma-separated) | `*` |
| `LOG_LEVEL` | | Log level (`DEBUG`/`INFO`/`WARNING`/`ERROR`) | `INFO` |

## Admin Panel

The admin panel is available at `/admin` and requires a Keycloak session.

### What you can configure

| Section | What you can do |
|---------|----------------|
| **Appearance** | App emoji, header title, hero text — changes reflected instantly without restart |
| **News** | Add, edit, publish/unpublish news entries shown on the home page |
| **Limits** | `MAX_CONCURRENT_SIMS`, `JOB_TIMEOUT`, `JOBS_TTL` — adjustable at runtime |
| **Tasks** | View active/running simulation jobs, cancel a stuck job |
| **Health** | Check status of PostgreSQL, SimulationCraft binary, results directory |
| **Logs** | Browse structured application logs by level (INFO/WARNING/ERROR) |

### Appearance config

Appearance is stored in `appearance.json` in the results directory and served via `GET /api/appearance` (public, no auth required). The frontend fetches it on every page load.

Example `appearance.json`:
```json
{
  "emoji": "⚔️",
  "header_title": "SimCraft Web",
  "hero_title": "WoW DPS Simulator"
}
```

## Internationalization (i18n)

The app supports multiple languages via `frontend/locales/*.json` files and the Alpine.js `$store.i18n` store.

### Adding a new language

1. Copy `frontend/locales/en.json` to e.g. `frontend/locales/de.json`
2. Translate all values (keys must stay the same)
3. In `frontend/i18n.js`, add `'de'` to the `SUPPORTED_LANGS` array
4. Add a language switcher button in `index.html` and `result.html`

### Using translations in HTML

```html
<!-- Simple key -->
<span x-text="$store.i18n.t('header.profile')"></span>

<!-- Key with interpolation -->
<span x-text="$store.i18n.t('header.characters_count', { count: 5 })"></span>
```

### Translation file structure

```
locales/
  pl.json   — Polish (default)
  en.json   — English
```

Top-level keys: `meta`, `header`, `nav`, `lang`, `common`, `home`, `sim`, `result`, `chars`, `history`, `news`, `profile`, `errors`.

## Architecture

```
Browser
  │
  ├── Alpine.js (frontend) ───────────────────────────┐
  │   Views: home / symulacje / profil / ustawienia / ulubione   │
  │   Mixins: SimMixin, CharsMixin, HistoryMixin                  │
  └───────────────────────────────────────────────────┘
          │ HTTP (REST)
  ┌───────┴───────┐
  │  FastAPI backend  │
  │  (Python 3.10+)   │
  │                   │
  │  auth.py          │───► Battle.net OAuth2
  │  characters.py    │───► Blizzard API (armory)
  │  simulation.py    │───► simc binary (subprocess)
  │  results.py       │───► Plotly/kaleido (PNG charts)
  │  history.py       │┌
  │  reactions.py     ││
  │  rankings.py      ││
  │  profiles.py      ││
  │  favorites.py     ││─► PostgreSQL (SQLAlchemy)
  │  admin.py         ││          tables: users, sessions,
  │  database.py      │┘          history, jobs, reactions,
  └─────────────────┘          news, admin_logs, favorites
```

## Project Structure

```
simcraft-web/
├── backend/
│   ├── main.py            # FastAPI app, routing, OG meta, startup
│   ├── auth.py            # Battle.net OAuth2; fetches bnet_id from /userinfo
│   ├── characters.py      # Blizzard character API (list, media, equipment, stats, talents)
│   ├── simulation.py      # simc runner, job queue, watchdog
│   ├── results.py         # JSON result parsing, PNG chart generation (Plotly/kaleido)
│   ├── history.py         # Simulation history (tied to bnet_id), trends, metadata
│   ├── reactions.py       # Emoji reactions (GET/POST), toggle/swap logic
│   ├── rankings.py        # Rankings API (top 10, top 3 podium, meta)
│   ├── profiles.py        # Public user profiles GET /api/profile/{bnet_id}
│   ├── favorites.py       # Favorites system (add/remove/list/check); ensure_table() on startup
│   ├── database.py        # SQLAlchemy models + inline migrations
│   ├── admin.py           # Admin panel (Keycloak), news, logs, limits, appearance
│   └── logging_config.py  # Structured logging (structlog)
├── frontend/
│   ├── index.html         # Main SPA shell
│   ├── result.html        # Result page (OG meta, spell breakdown, chart, reactions)
│   ├── rankings.html      # Rankings page (podium + table, filters)
│   ├── profile.html       # Public user profile page (/u/{bnet_id})
│   ├── admin.html         # Admin panel
│   ├── app.js             # Alpine.js root; view router (loadView/navigateTo/handleHash)
│   ├── sim.js             # Simulation form logic (SimMixin)
│   ├── chars.js           # Character list, equipment, talents (CharsMixin)
│   ├── history.js         # History widget (HistoryMixin)
│   ├── settings.js        # Settings mixin (main char, privacy, theme, language)
│   ├── favorites.js       # favoritesView() Alpine component for /#ulubione
│   ├── header.js          # Header mixin (session, dropdown)
│   ├── api.js             # API client (fetch wrapper)
│   ├── utils.js           # Helpers (number formatting, class colors, etc.)
│   ├── admin.js           # Admin panel logic
│   ├── i18n.js            # Translation system (Alpine store, auto-detect, localStorage)
│   ├── style.css          # Global styles (design tokens, dark/light theme, components)
│   ├── views/
│   │   ├── home.html        # Home view (hero, addon form, top 3 podium, public history, news)
│   │   ├── symulacje.html   # Simulations view (character list, form, results, history)
│   │   ├── profil.html      # Profile view (characters, history, DPS trend chart)
│   │   ├── ulubione.html    # Favorites view (grid of favorited profiles)
│   │   └── ustawienia.html  # Settings view (main char select, privacy, theme, language)
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
- **Exception:** views that need isolated state (e.g. `ulubione.html`) use `x-data="favoritesView()"` but the function **must be defined globally** (in a `<script>` loaded in `index.html`) before Alpine boots — inline `<script>` inside `innerHTML` is not executed by the browser
- Mixins (`SimMixin`, `CharsMixin`, `HistoryMixin`) are merged by `mergeMixins()` which uses `Object.defineProperties` — this ensures getters (e.g. `sortedSpells`, `filteredChars`) are correctly copied with their descriptors preserved
- Getters referencing `this.*` must be defined directly in the `state` object in `app()`, not in mixins — `...spread` destroys getter descriptors
- Valid hash routes: `#symulacje`, `#profil`, `#ustawienia`, `#ulubione`
- `rankings.html` and `profile.html` are **standalone pages** (not views), served by FastAPI at `GET /rankings` and `GET /u/{bnet_id}`
- **State property names matter** — views use the actual state field names (e.g. `loadingHistory`, not aliases); aliased names are not visible after `Alpine.initTree()`

## CSS Design Tokens

All visual constants are defined as CSS custom properties in `:root` and overridden in `[data-theme="light"]`:

| Token | Dark | Light | Usage |
|-------|------|-------|-------|
| `--accent` | `#c89a3c` | `#a07820` | Primary brand color, active tabs, CTA buttons |
| `--accent2` | `#7c5cfc` | `#5a3fd4` | Secondary accent, public char buttons |
| `--danger` | `#c0392b` | `#e74c3c` | Destructive actions, private char buttons, active segment buttons |
| `--bg` | `#0d0e12` | `#f4f5f7` | Page background |
| `--surface` | `#1a1b22` | `#ffffff` | Card/panel background |
| `--border` | `#2e3040` | `#d0d4e0` | Borders, dividers |
| `--text` | `#e8e8f0` | `#1a1b22` | Body text |
| `--muted` | `#8888aa` | `#666688` | Secondary text, labels |

## API Reference

### Simulation
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/simulate` | Run a simulation |
| `GET` | `/api/job/{job_id}` | Job status (`running` / `done` / `error`) |
| `GET` | `/api/result/{job_id}/json` | Results in JSON format |
| `GET` | `/api/result/{job_id}/dps-chart.png` | DPS chart as PNG |
| `GET` | `/api/result/{job_id}/meta` | Simulation metadata (character, class, fight style) |
| `GET` | `/api/result/{job_id}/csv` | Spell breakdown as CSV |

### History
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/history` | Public history (pagination: `?page=1&limit=50`) |
| `GET` | `/api/history/mine` | Logged-in user's history (filtered by `bnet_id`) |
| `GET` | `/api/history/trend` | DPS over time for a specific character (`?name=...&fight_style=...`) |

### Rankings
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/rankings` | Top 10 per fight style/class/spec; one entry per unique character (`?fight_style=&character_class=&character_spec=&limit=10`) |
| `GET` | `/api/rankings/top3` | Top 3 for home page podium (`?fight_style=Patchwerk`) |
| `GET` | `/api/rankings/meta` | Available classes, specs, fight styles for filter dropdowns |

### Reactions
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/reactions/{job_id}` | Get reaction counts + current user's reaction (`?session=...`) |
| `POST` | `/api/reactions/{job_id}` | Set/change/remove reaction (toggle = same emoji removes it) |

### Characters
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/characters` | Account character list (requires session) |
| `GET` | `/api/character-media` | Character avatar |
| `GET` | `/api/character/equipment` | Character equipment |
| `GET` | `/api/character/statistics` | Character statistics |
| `GET` | `/api/character/talents` | Character talents |

### Profiles
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/profile/{bnet_id}` | Public profile (main char, best DPS, sim count, history); 404 if private |

### Favorites
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/favorites` | List of favorited profiles for the logged-in user (`?session=...`) |
| `POST` | `/api/favorites/{bnet_id}` | Add a profile to favorites (`?session=...`) |
| `DELETE` | `/api/favorites/{bnet_id}` | Remove a profile from favorites (`?session=...`) |
| `GET` | `/api/favorites/check/{bnet_id}` | Check if a profile is in the user's favorites (`?session=...`) |

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/auth/login` | Redirect to Battle.net OAuth |
| `GET` | `/auth/callback` | OAuth callback (fetches `bnet_id` from `/userinfo`) |
| `GET` | `/auth/logout` | Logout |
| `GET` | `/auth/session/info` | Session info (main character, bnet_id, is_first_login) |
| `GET` | `/auth/session/settings` | Get user settings (main char, privacy) |
| `PATCH` | `/auth/session/settings` | Save user settings |
| `PATCH` | `/auth/session/main-character` | Set main character |
| `POST` | `/auth/session/skip-first-login` | Skip main character selection modal |

### Admin
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/admin` | Admin panel (requires Keycloak session) |
| `GET` | `/admin/api/limits` | Get system limits |
| `PATCH` | `/admin/api/limits` | Update system limits |
| `GET` | `/admin/api/health` | Service health check |
| `GET` | `/admin/api/tasks` | List active jobs |
| `DELETE` | `/admin/api/tasks/{job_id}` | Cancel a job |
| `GET` | `/api/appearance` | Get appearance config (public) |
| `PATCH` | `/admin/api/appearance` | Update appearance config |

## Database Schema

| Table | Description |
|-------|-------------|
| `users` | Battle.net accounts; stores `bnet_id`, main character, privacy settings |
| `sessions` | Active OAuth sessions; sliding 30-day TTL extended on every active use |
| `history` | All simulation results; tied to `bnet_id` or guest |
| `jobs` | Simulation job queue; status tracking |
| `reactions` | Emoji reactions per `job_id`; `UNIQUE(job_id, user_key)` |
| `news` | News entries managed from admin panel |
| `admin_logs` | Structured application logs |
| `admin_sessions` | Keycloak admin sessions |
| `favorites` | Favorited profiles; `UNIQUE(user_bnet_id, target_bnet_id)`; created via `ensure_table()` on startup |

> Migrations are applied automatically via `init_db()` on startup using `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` — no migration tool needed.

## License

MIT
