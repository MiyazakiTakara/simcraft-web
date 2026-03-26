# API Reference

Wszystkie endpointy API działają pod prefiksem `/api/`.
Endpointy admina działają pod `/admin/api/`.
Autoryzacja użytkowników odbywa się przez cookie sesji Keycloak (`kc_session`).

---

## Symulacje

### `POST /api/simulate`
Uruchamia nową symulację w tle.

**Auth:** opcjonalna (zalogowany user zapisuje do historii)

**Body:**
```json
{
  "simc_input": "warrior\nspec=fury\n...",
  "fight_style": "Patchwerk",
  "target_error": 0.5,
  "iterations": 10000,
  "fight_length": 300
}
```

**Response `201`:** `{ "job_id": "uuid4" }`

**Błędy:** `429` rate limit, `503` brak slotów, `422` nieprawidłowy input

---

### `GET /api/result/{job_id}/status`
Sprawdza status symulacji (polling).

**Response:** `{ "status": "queued|running|done|error", "progress": 0-100, "error": null }`

---

### `GET /api/result/{job_id}/meta`
Zwraca metadane wyniku.

---

### `GET /api/result/{job_id}/json`
Zwraca surowy JSON output simc (duży payload ~500KB-2MB).

---

## Historia

### `GET /api/history`
Historia symulacji zalogowanego użytkownika.

**Auth:** wymagana

**Query params:** `limit`, `offset`, `char_name`, `fight_style`

---

## Reakcje

### `POST /api/reactions/{job_id}`
Toggle reakcji. **Body:** `{ "emoji": "fire" }`

**Dostępne emoji:** `fire`, `strong`, `sad`, `skull`, `rofl`

### `GET /api/reactions/{job_id}`
Zliczenia reakcji dla danego wyniku.

---

## Rankingi

### `GET /api/rankings`
Top DPS globalnie lub z filtrami: `class`, `spec`, `fight_style`, `limit`, `realm`

---

## Ulubione

### `POST /api/favorites/{job_id}` — Dodaje do ulubionych
### `DELETE /api/favorites/{job_id}` — Usuwa z ulubionych
### `GET /api/favorites` — Lista ulubionych

---

## Admin API

Wszystkie endpointy `/admin/api/*` wymagają aktywnej sesji admina (cookie `admin_session`).

| Endpoint | Metoda | Opis |
|----------|--------|------|
| `/admin/api/dashboard` | GET | Statystyki ogólne + wykresy |
| `/admin/api/users` | GET | Lista użytkowników |
| `/admin/api/logs` | GET | Logi aplikacji (`?level=ERROR`) |
| `/admin/api/tasks` | GET | Aktywne symulacje |
| `/admin/api/tasks/{job_id}` | DELETE | Anulowanie zadania |
| `/admin/api/health` | GET | Status serwisów |
| `/admin/api/limits` | GET/PATCH | Limity symulacji |
| `/admin/api/news` | GET/POST | Zarządzanie newsami |
| `/admin/api/appearance` | GET/POST | Konfiguracja wyglądu |
| `/admin/api/docs` | GET | Lista plików dokumentacji (`?lang=pl`) |
| `/admin/api/docs/{filename}` | GET | Treść pliku `.md` (`?lang=pl`) |
