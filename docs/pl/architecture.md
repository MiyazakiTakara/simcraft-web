# Architektura SimCraft Web

Aplikacja działa jako zestaw kontenerów Docker zarządzanych przez Docker Compose.

## Stack technologiczny

| Warstwa | Technologia | Uwagi |
|---------|------------|-------|
| Backend API | FastAPI (Python 3.11) | async, Pydantic v2 |
| Frontend | Alpine.js + Vanilla JS | MPA (Multi-Page App) |
| Baza danych | PostgreSQL 15 | SQLAlchemy ORM |
| Reverse proxy | nginx | TLS termination, static files |
| Auth | Keycloak (OIDC) | OAuth2 + session cookie |
| Symulator | SimulationCraft (`simc`) | binary, branch `midnight` |
| Cache | In-memory (Python dict) | wersja simc, appearance config |

## Kontenery (docker-compose.yml)

- **app** — FastAPI na porcie `8000` wewnętrznie
- **db** — PostgreSQL 15, wolumen `pgdata`
- **nginx** — reverse proxy, porty `80`/`443`, TLS (certbot/Let's Encrypt)
- **keycloak** — OIDC provider na porcie `8080` wewnętrznie

## Struktura katalogów

```
simcraft-web/
├── backend/
│   ├── main.py
│   ├── admin.py
│   ├── admin_docs.py
│   ├── simulation.py
│   ├── results.py
│   ├── history.py
│   ├── rankings.py
│   ├── reactions.py
│   ├── characters.py
│   ├── profiles.py
│   ├── favorites.py
│   ├── icons.py
│   ├── auth.py
│   ├── database.py
│   └── traffic.py
├── frontend/
│   ├── admin.html
│   ├── admin-v2.html
│   ├── admin/
│   ├── admin-v2/
│   ├── result.html
│   ├── sim.html
│   ├── rankings.html
│   ├── profile.html
│   ├── locales/
│   └── static/
├── docs/
│   ├── pl/
│   └── en/
├── config/
├── nginx/
└── docker-compose.yml
```

## Przepływ symulacji

```
User → nginx → FastAPI POST /api/simulate
  → walidacja simc_input
  → sprawdzenie rate limit (5 req/min per user)
  → sprawdzenie MAX_CONCURRENT_SIMS
  → zapis JobModel (status: queued) do PostgreSQL
  → asyncio task w tle
      → subprocess: simc input_file.simc json_file=output.json
      → parsowanie przez simc_parser.py
      → zapis do /app/results/{job_id}.json
      → zapis do HistoryEntryModel
      → aktualizacja JobModel (status: done)
  → polling GET /api/result/{job_id}/status co 2s
```

## Modele bazy danych

| Model | Tabela | Opis |
|-------|--------|------|
| `JobModel` | `jobs` | Status zadania symulacji |
| `HistoryEntryModel` | `history` | Wyniki symulacji z metadanymi |
| `NewsModel` | `news` | Newsy |
| `LogEntryModel` | `logs` | Logi aplikacji |
| `AdminSessionModel` | `admin_sessions` | Sesje admina |
| `PageVisitModel` | `page_visits` | Tracking ruchu |
| `ReactionModel` | `reactions` | Emoji reakcje |
| `FavoriteModel` | `favorites` | Ulubione symulacje |
