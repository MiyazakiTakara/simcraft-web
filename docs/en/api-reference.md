# API Reference

All API endpoints operate under the `/api/` prefix.
Admin endpoints operate under `/admin/api/`.
User authorization is handled via the Keycloak session cookie (`kc_session`).

---

## Simulations

### `POST /api/simulate`
Starts a new simulation in the background.

**Auth:** optional (logged-in users save results to history)

**Body:**
```json
{
  "simc_input": "warrior\nspec=fury\n...",
  "fight_style": "Patchwerk",
  "target_error": 0.5,
  "iterations": 10000,
  "fight_length": 300,
  "one_button_mode": false
}
```

**Response `201`:** `{ "job_id": "uuid4" }`

**Errors:** `429` rate limit, `503` no available slots, `422` invalid input

---

### `GET /api/result/{job_id}/status`
Checks simulation status (for polling).

**Response:** `{ "status": "queued|running|done|error", "progress": 0-100, "error": null }`

---

### `GET /api/result/{job_id}/meta`
Returns result metadata.

**Response:**
```json
{
  "job_id": "...",
  "character_name": "Takara",
  "character_class": "Warrior",
  "character_spec": "Fury",
  "character_realm": "tarren-mill",
  "dps": 154321.5,
  "avg_item_level": 639,
  "fight_style": "Patchwerk",
  "fight_length": 300,
  "one_button_mode": false,
  "talents": "BIQAAAAAAAAAAAAAAAAAAAAAtpkSSJJJlkSSSSJSSA",
  "items": [{"slot": "head", "name": "...", "item_id": 12345, "ilvl": 642}],
  "buff_uptime": [{"name": "Enrage", "uptime": 0.82}],
  "author_name": "MiyazakiTakara",
  "author_bnet_id": "..."
}
```

---

### `GET /api/result/{job_id}/json`
Returns the raw simc JSON output (large payload ~500KB–2MB).

---

## History

### `GET /api/history`
Simulation history for the logged-in user.

**Auth:** required

**Query params:**
| Param | Type | Description |
|-------|------|-------------|
| `limit` | int | Max results (default 20) |
| `offset` | int | Pagination offset |
| `char_name` | string | Filter by character name |
| `fight_style` | string | Filter by fight style |

---

### `GET /api/history/public`
Public history (latest public simulations from all users).

**Query params:** `limit`, `offset`

---

## Reactions

### `POST /api/reactions/{job_id}`
Toggle reaction (adds if not present, removes if it exists).

**Auth:** required

**Body:** `{ "emoji": "fire" }`

**Available emoji:** `fire`, `strong`, `sad`, `skull`, `rofl`

---

### `GET /api/reactions/{job_id}`
Reaction counts for a given result.

**Response:** `{ "fire": 3, "skull": 1, "strong": 2 }` (zero values omitted)

---

## Rankings

### `GET /api/rankings`
Top DPS globally or with filters.

**Query params:**
| Param | Type | Description |
|-------|------|-------------|
| `class` | string | Character class (e.g. `Warrior`) |
| `spec` | string | Specialization (e.g. `Fury`) |
| `fight_style` | string | Fight style |
| `limit` | int | Max results (default 100) |
| `realm` | string | Filter by realm |

---

## Favorites

### `POST /api/favorites/{job_id}`
Adds a simulation to favorites.

### `DELETE /api/favorites/{job_id}`
Removes from favorites.

### `GET /api/favorites`
List of favorites for the logged-in user.

---

## Icons

### `GET /api/icon/{icon_name}`
Proxy for spell/item icons from Blizzard CDN. Cached locally.

### `GET /api/icon-by-item/{item_id}`
Returns an item icon by item ID.

---

## Appearance (public)

### `GET /api/appearance`
Returns the current site appearance configuration.

**Response:** `{ "header_title": "SimCraft Web", "hero_title": "...", "emoji": "⚔️", "hero_custom_text": "" }`

---

## Admin API

All `/admin/api/*` endpoints require an active admin session (cookie `admin_session`).

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/admin/api/dashboard` | GET | General stats + charts |
| `/admin/api/users` | GET | User list with sim_count |
| `/admin/api/users/{id}/simulations` | GET | User simulation history |
| `/admin/api/logs` | GET | Application logs (`?level=ERROR`) |
| `/admin/api/tasks` | GET | Active simulations |
| `/admin/api/tasks/{job_id}` | DELETE | Cancel a task |
| `/admin/api/health` | GET | Service status |
| `/admin/api/limits` | GET/PATCH | Simulation limits |
| `/admin/api/config` | GET/PATCH | App config (e.g. history display limits) |
| `/admin/api/news` | GET/POST | News management |
| `/admin/api/news/{id}` | PATCH/DELETE | Edit/delete a news item |
| `/admin/api/appearance` | GET/POST | Appearance configuration |
| `/admin/api/traffic/stats` | GET | Traffic statistics |
| `/admin/api/docs` | GET | List documentation files (`?lang=en`) |
| `/admin/api/docs/{filename}` | GET | Get `.md` file content (`?lang=en`) |
| `/admin/api/client-error` | POST | Report JS errors (rate-limited) |
