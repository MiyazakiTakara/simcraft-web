# SimCraft Web

Webowy symulator DPS dla World of Warcraft oparty na SimulationCraft.

## Funkcje

- **Logowanie przez Battle.net** — autoryzacja OAuth2, pobieranie postaci z armory
- **Symulacje z Armory** — automatyczne pobieranie danych postaci z API Blizzarda
- **Symulacje z Addon Export** — możliwość wklejenia tekstu z addona SimulationCraft bez logowania
- **Historia symulacji** — zapis wszystkich symulacji, publiczna lista ostatnich wyników
- **Wykresy DPS** — interaktywne wykresy kołowe (plotly)
- **Panel admina** — zarządzanie newsami, limitami, health check, zadaniami (Keycloak OAuth2)
- **Rate limiting** — ochrona przed nadużywaniem API

## TODO

### Funkcje społecznościowe

> ⚠️ Wymagają przemyślenia systemu tożsamości użytkowników — aktualnie użytkownicy identyfikowani są przez UUID sesji Battle.net, bez żadnej nazwy wyświetlanej ani profilu. Przed implementacją poniższych funkcji warto rozważyć: czy wystarczy wyświetlać nick postaci WoW (np. `Thrall-Draenor`), czy potrzebny jest osobny profil użytkownika?

- [ ] **Profile użytkowników** — strona `/u/{battletag_lub_uuid}` z historią symulacji danej osoby, ulubionymi postaciami, statystykami
- [ ] **Rankingi** — tabela TOP DPS per klasa/spec/fight style, aktualizowana na bieżąco z historii
- [ ] **Komentarze / reakcje** — możliwość zostawienia komentarza lub emoji-reakcji pod wynikiem symulacji (powiązanym z `job_id`)
- [ ] **Udostępnianie buildów** — eksport konfiguracji symulacji (addon text + parametry) jako publiczny link do ponownego uruchomienia
- [ ] **Porównywanie symulacji** — widok `/compare?a={job_id}&b={job_id}` z diff-em spelli i DPS obok siebie
- [ ] **Obserwowanie postaci** — zapisanie postaci do "ulubionych" i śledzenie jej historii DPS na wykresie trendów

### Techniczne

- [ ] **Race condition w `simulation.py`** — `out_path` czytany z `jobs[]` poza `_running_lock`; przekazać jako argument do `_run_sim()`
- [ ] **Pinowanie wersji w `requirements.txt`** — zastąpić unpinned dependencies wynikiem `pip freeze`
- [ ] **Eksport wyników CSV** — endpoint `GET /api/result/{job_id}/csv` zwracający breakdown spelli jako CSV

## Wymagania

- Python 3.10+
- PostgreSQL
- Docker & Docker Compose (opcjonalnie)
- Konto deweloperskie Battle.net (OAuth)
- Keycloak (dla panelu admina)

## Uruchomienie lokalne

### Docker Compose

```bash
cp .env.example .env
# edytuj .env i uzupełnij zmienne środowiskowe

docker-compose up --build
```

### Ręcznie

```bash
# Zbuduj SimulationCraft
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
# ... pozostałe zmienne środowiskowe

cd backend
uvicorn main:app --reload
```

## Zmienne środowiskowe

| Zmienna | Opis |
|---------|------|
| `BLIZZARD_CLIENT_ID` | ID aplikacji OAuth Battle.net |
| `BLIZZARD_CLIENT_SECRET` | Secret aplikacji OAuth Battle.net |
| `REDIRECT_URI` | URL powrotny po autoryzacji Battle.net |
| `DATABASE_URL` | Connection string PostgreSQL |
| `KEYCLOAK_URL` | URL Keycloak (dla admina) |
| `KEYCLOAK_REALM` | Realm Keycloak |
| `KEYCLOAK_CLIENT_ID` | Client ID Keycloak |
| `KEYCLOAK_CLIENT_SECRET` | Client Secret Keycloak |
| `ADMIN_REDIRECT_URI` | URL powrotny po logowaniu admina |
| `RESULTS_DIR` | Katalog na wyniki symulacji (domyślnie /app/results) |
| `SIMC_PATH` | Ścieżka do binary simc (domyślnie /app/SimulationCraft/simc) |
| `MAX_CONCURRENT_SIMS` | Maksymalna liczba równoczesnych symulacji (domyślnie 3) |
| `JOB_TIMEOUT` | Timeout symulacji w sekundach (domyślnie 360) |

## Struktura projektu

```
simcraft-web/
├── backend/
│   ├── main.py          # FastAPI app, routing
│   ├── auth.py          # Battle.net OAuth
│   ├── characters.py    # API postaci Blizzarda
│   ├── simulation.py    # Uruchamianie symulacji simc
│   ├── results.py       # Parsowanie wyników, wykresy
│   ├── history.py       # Historia symulacji
│   ├── database.py      # Modele SQLAlchemy
│   └── admin.py         # Panel admina (Keycloak)
├── frontend/
│   ├── index.html       # Główna strona
│   ├── admin.html       # Panel admina
│   ├── result.html      # Strona wyniku (dla social sharing)
│   ├── app.js           # Logika Alpine.js
│   ├── api.js           # API client
│   ├── admin.js         # Logika panelu admina
│   └── style.css        # Style
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## API

- `POST /api/simulate` — uruchomienie symulacji
- `GET /api/job/{job_id}` — status jobu
- `GET /api/result/{job_id}/json` — wyniki JSON
- `GET /api/result/{job_id}/dps-chart.png` — wykres DPS
- `GET /api/history` — publiczna historia
- `GET /api/history/mine` — historia zalogowanego
- `GET /api/characters` — lista postaci (wymaga sesji)
- `GET /auth/login` — logowanie Battle.net
- `GET /admin` — panel admina
- `GET /admin/api/limits` — pobierz limity systemowe
- `PATCH /admin/api/limits` — aktualizuj limity systemowe
- `GET /admin/api/health` — health check usług
- `GET /admin/api/tasks` — lista aktywnych zadań
- `DELETE /admin/api/tasks/{job_id}` — anuluj zadanie

## Licencja

MIT
