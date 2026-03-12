# SimCraft Web

> 🇬🇧 [English README](./README.md)

Webowy symulator DPS dla World of Warcraft oparty na SimulationCraft.

> Aplikacja jest **DPS-only** — symulacje healerów i tanków nie są obsługiwane.

## Funkcje

- **Logowanie przez Battle.net** — autoryzacja OAuth2, pobieranie postaci z armory
- **Symulacje z Armory** — automatyczne pobieranie danych postaci z API Blizzarda
- **Symulacje z Addon Export** — możliwość wklejenia tekstu z addona SimulationCraft bez logowania
- **Historia symulacji** — zapis wszystkich symulacji powiązany z kontem Battle.net (działa między przeglądarkami i sesjami); publiczna lista ostatnich wyników z paginacją
- **Wykresy DPS** — wykresy kółkowe Total DMG + DPS (Plotly/kaleido, renderowane server-side do PNG)
- **Social sharing** — każdy wynik ma unikalny URL z OG meta tagami (podgląd na Discordzie, Twitterze itp.)
- **Panel admina** — zarządzanie newsami, limitami symulacji, health check, lista aktywnych zadań (Keycloak OAuth2)
- **Rate limiting** — ochrona przed nadużywaniem API (slowapi, per-IP)
- **Watchdog** — automatyczne czyszczenie starych jobów i obsługa timeoutów
- **Wielojęzyczność** — pełne i18n PL/EN z przełącznikiem języka, auto-detekcją z przeglądarki i zapisem w `localStorage`
- **Główna postać (main char)** — modal przy pierwszym logowaniu; zapis trwały do tabeli `users` powiązanej z `bnet_id`; wyświetlanie w headerze
- **Dropdown menu użytkownika** — rozwijane menu pod imieniem głównej postaci: Postacie, Historia, Ustawienia, Wyloguj
- **Persist widoku** — aktywny widok zapisywany w URL hash (`#symulacje`, `#profil`, `#ustawienia`); obsługa przycisku wstecz/dalej przeglądarki

## TODO

### Historia symulacji

- [ ] **Ukrycie wyników symulacji gości z publicznej historii** — symulacje wykonane bez logowania (addon export na stronie głównej) nie powinny pojawiać się w publicznej liście historii. Wynik powinien być nadal dostępny bezpośrednio przez link `/result/{job_id}`. Wymagane zmiany:
  - Backend: przy zapisie do historii dodać flagę `is_guest: bool` (lub `user_id IS NULL` jako wyznacznnik); endpoint `GET /api/history` powinien filtrować wpisy gdzie `is_guest = true`
  - Frontend: `startGuestSim()` w `sim.js` może w ogóle nie wywoływać `API.saveToHistory()`, albo przekazywać flagę gościa — do ustalenia

### Funkcje społecznościowe

- [ ] **Profile użytkowników** — strona `/u/{realm}/{name}` z historią symulacji, wybrana główna postać jako awatar profilu
- [ ] **Rankingi** — tabela TOP DPS per klasa/spec/fight style, generowana z publicznej historii
- [ ] **Komentarze / reakcje** — emoji-reakcje lub krótki komentarz pod wynikiem symulacji (per `job_id`)
- [ ] **Udostępnianie buildów** — eksport konfiguracji symulacji (addon text + parametry) jako publiczny link do ponownego uruchomienia
- [ ] **Porównywanie symulacji** — widok `/compare?a={job_id}&b={job_id}` z diff-em spelli i DPS obok siebie
- [ ] **Śledzenie trendów** — wykres DPS w czasie dla konkretnej postaci (endpoint `/api/history/trend` już istnieje, brakuje UI)

### Ustawienia

- [ ] **Strona ustawień** — zmiana głównej postaci, preferencje języka, motyw (`views/ustawienia.html` aktualnie WIP placeholder)

### Techniczne

- [x] **Race condition w `simulation.py`** — `out_path` przekazywany jako argument do `_run_sim()`, nie jest czytany z `jobs[]` poza lockiem
- [x] **Gettery Alpine.js w mixa-ach** — `sortedSpells`, `filteredChars`, `pagedHistory`, `pagedNews` itp. muszą być definiowane przez `Object.defineProperties` (przez `mergeMixins`), nie przez `...spread`
- [x] **Pinowanie wersji w `requirements.txt`** — wszystkie 13 zależności używają dokładnego pinowania `==`
- [x] **Persist widoku po refresh** — aktywna zakładka zapisywana w URL hash; odczytywana w `init()` przez `handleHash()`
- [x] **Główna postać zapisana do konta Battle.net** — tabela `users` z kluczem `bnet_id`; pobierane z `/userinfo` przy każdym logowaniu
- [x] **Historia symulacji powiązana z bnet_id** — `history.user_id` przechowuje `bnet_id` zamiast `session_id`; historia widoczna po ponownym logowaniu
- [ ] **Eksport wyników CSV** — endpoint `GET /api/result/{job_id}/csv` zwracający breakdown spelli

## Wymagania

- Python 3.10+
- PostgreSQL
- Docker & Docker Compose (zalecane)
- Konto deweloperskie Battle.net (OAuth2)
- Keycloak (dla panelu admina)

## Uruchomienie lokalne

### Docker Compose

```bash
cp .env.example .env
# edytuj .env i uzupełnij zmienne środowiskowe

docker compose up --build
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
# ... pozostałe zmienne środowiskowe (patrz .env.example)

cd backend
uvicorn main:app --reload
```

## Zmienne środowiskowe

| Zmienna | Opis | Domyślnie |
|---------|------|----------|
| `BLIZZARD_CLIENT_ID` | ID aplikacji OAuth Battle.net | — |
| `BLIZZARD_CLIENT_SECRET` | Secret aplikacji OAuth Battle.net | — |
| `REDIRECT_URI` | URL powrotny po autoryzacji Battle.net | — |
| `DATABASE_URL` | Connection string PostgreSQL | `postgresql://simcraft:simcraft@db:5432/simcraft` |
| `KEYCLOAK_URL` | URL Keycloak (dla admina) | — |
| `KEYCLOAK_REALM` | Realm Keycloak | — |
| `KEYCLOAK_CLIENT_ID` | Client ID Keycloak | — |
| `KEYCLOAK_CLIENT_SECRET` | Client Secret Keycloak | — |
| `ADMIN_REDIRECT_URI` | URL powrotny po logowaniu admina | — |
| `BASE_URL` | Bazowy URL aplikacji (używany w OG meta tagach) | `https://sim.miyazakitakara.ovh` |
| `RESULTS_DIR` | Katalog na wyniki symulacji | `/app/results` |
| `SIMC_PATH` | Ścieżka do binary simc | `/app/SimulationCraft/simc` |
| `MAX_CONCURRENT_SIMS` | Maks. liczba równoczesnych symulacji | `3` |
| `JOB_TIMEOUT` | Timeout symulacji w sekundach | `360` |
| `JOBS_TTL` | Czas życia zakończonych jobów w pamięci (sekundy) | `14400` (4h) |
| `LOG_LEVEL` | Poziom logowania | `INFO` |

## Struktura projektu

```
simcraft-web/
├── backend/
│   ├── main.py            # FastAPI app, routing, OG meta, startup
│   ├── auth.py            # Battle.net OAuth2; pobiera bnet_id z /userinfo
│   ├── characters.py      # API postaci Blizzarda (lista, media, ekwipunek, statystyki, talenty)
│   ├── simulation.py      # Uruchamianie simc, kolejka jobów, watchdog
│   ├── results.py         # Parsowanie wyników JSON, generowanie wykresów PNG
│   ├── history.py         # Historia symulacji (powiązana z bnet_id), trendy, metadane
│   ├── database.py        # Modele SQLAlchemy (users, sessions, history, jobs), migracje inline
│   ├── admin.py           # Panel admina (Keycloak), newsy, logi, limity
│   └── logging_config.py  # Strukturowane logowanie (structlog)
├── frontend/
│   ├── index.html         # Główna strona
│   ├── result.html        # Strona wyniku (OG meta, spell breakdown, chart)
│   ├── admin.html         # Panel admina
│   ├── app.js             # Logika Alpine.js; router widoków (loadView/navigateTo/handleHash)
│   ├── sim.js             # Logika formularza symulacji (SimMixin)
│   ├── chars.js           # Lista postaci, ekwipunek, talenty (CharsMixin)
│   ├── history.js         # Widget historii (HistoryMixin)
│   ├── api.js             # API client (fetch wrapper)
│   ├── utils.js           # Helpers (formatowanie liczb, kolorów klas itp.)
│   ├── admin.js           # Logika panelu admina
│   ├── i18n.js            # System tłumaczeń (Alpine store, auto-detect, localStorage)
│   ├── style.css          # Style (dark theme)
│   ├── views/
│   │   ├── home.html        # Widok strony głównej (hero, addon form, historia publiczna, newsy)
│   │   ├── symulacje.html   # Widok symulacji (lista postaci, formularz, wyniki, historia)
│   │   ├── profil.html      # Widok profilu użytkownika (zakładki: Postacie, Historia)
│   │   └── ustawienia.html  # Widok ustawień (WIP)
│   └── locales/
│       ├── pl.json          # Tłumaczenia PL
│       └── en.json          # Tłumaczenia EN
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## Architektura frontendu

Frontend używa **Alpine.js** z wzorcem miksynów. Ważne zasady:

- `app()` jest jedynym Alpine `x-data` na stronie głównej
- Widoki (`views/*.html`) są ładowane dynamicznie przez `loadView(name)` do `#view-container` i inicjowane przez `Alpine.initTree()` — **nie mają własnego `x-data`**, działają w scope rodzica
- Miksyny (`SimMixin`, `CharsMixin`, `HistoryMixin`) są mergowane przez `mergeMixins()` która używa `Object.defineProperties` — dzięki temu gettery są poprawnie kopiowane z zachowaniem deskryptorów
- Gettery które odwołują się do `this.*` muszą być zdefiniowane bezpośrednio w obiekcie `state` w `app()`, nie w mixa-ach
- Poprawne trasy hash: `#symulacje`, `#profil`, `#ustawienia`

## API

### Symulacja
- `POST /api/simulate` — uruchomienie symulacji
- `GET /api/job/{job_id}` — status jobu (`running` / `done` / `error`)
- `GET /api/result/{job_id}/json` — wyniki w formacie JSON
- `GET /api/result/{job_id}/dps-chart.png` — wykres DPS jako PNG
- `GET /api/result/{job_id}/meta` — metadane symulacji (postać, klasa, fight style)

### Historia
- `GET /api/history` — publiczna historia (paginacja: `?page=1&limit=50`)
- `GET /api/history/mine` — historia zalogowanego użytkownika (filtrowana po `bnet_id`)
- `GET /api/history/trend` — historia DPS w czasie dla konkretnej postaci

### Postacie
- `GET /api/characters` — lista postaci konta (wymaga sesji)
- `GET /api/character-media` — awatar postaci
- `GET /api/character/equipment` — ekwipunek postaci
- `GET /api/character/statistics` — statystyki postaci
- `GET /api/character/talents` — talenty postaci

### Auth
- `GET /auth/login` — redirect do Battle.net OAuth
- `GET /auth/callback` — callback OAuth (pobiera `bnet_id` z `/userinfo`)
- `GET /auth/logout` — wylogowanie
- `GET /auth/session/info` — info o sesji (główna postać, is_first_login)
- `PATCH /auth/session/main-character` — ustawienie głównej postaci
- `POST /auth/session/skip-first-login` — pomij modal wyboru głównej postaci

### Admin
- `GET /admin` — panel admina (wymaga sesji Keycloak)
- `GET /admin/api/limits` — pobierz limity systemowe
- `PATCH /admin/api/limits` — aktualizuj limity systemowe
- `GET /admin/api/health` — health check usług
- `GET /admin/api/tasks` — lista aktywnych zadań
- `DELETE /admin/api/tasks/{job_id}` — anuluj zadanie

## Licencja

MIT
