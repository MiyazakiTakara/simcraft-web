# SimCraft Web

Webowy symulator DPS dla World of Warcraft oparty na SimulationCraft.

> Aplikacja jest **DPS-only** — symulacje healerów i tanków nie są obsługiwane.

## Funkcje

- **Logowanie przez Battle.net** — autoryzacja OAuth2, pobieranie postaci z armory
- **Symulacje z Armory** — automatyczne pobieranie danych postaci z API Blizzarda
- **Symulacje z Addon Export** — możliwość wklejenia tekstu z addona SimulationCraft bez logowania
- **Historia symulacji** — zapis wszystkich symulacji, publiczna lista ostatnich wyników z paginacją
- **Wykresy DPS** — wykresy kółowe Total DMG + DPS (Plotly/kaleido, renderowane server-side do PNG)
- **Social sharing** — każdy wynik ma unikalny URL z OG meta tagami (podgląd na Discordzie, Twitterze itp.)
- **Panel admina** — zarządzanie newsami, limitami symulacji, health check, lista aktywnych zadań (Keycloak OAuth2)
- **Rate limiting** — ochrona przed nadużywaniem API (slowapi, per-IP)
- **Watchdog** — automatyczne czyszczenie starych jobów i obsługa timeoutów
- **Wielojęzyczność** — pełne i18n PL/EN z przełącznikiem języka, auto-detekcją z przeglądarki i zapisem w `localStorage`
- **Główna postać (main char)** — przy pierwszym logowaniu modal z wyborem głównej postaci; zapis do sesji; wyświetlanie w headerze

## TODO

### Nawigacja

- [ ] **Persist widoku po refresh** — przy odświeżeniu strony użytkownik powinien trafić z powrotem do tego samego widoku (home/symulacje/profil). Aktualnie zawsze wraca na `home`. Proponowane rozwiązanie: zapis aktywnej zakładki w `localStorage` lub URL hash (`#symulacje`) i odczyt w `init()`.

### Funkcje społecznościowe

> **Problem tożsamości użytkowników:** Użytkownicy logują się przez Battle.net OAuth i posiadają wiele postaci. Planowane podejście: przy pierwszym logowaniu użytkownik wybiera **główną postać** (main), która staje się jego profilem publicznym. Wszystkie symulacje są nadal przypisane do konta (session UUID), ale publicznie wyświetlany jest nick w formacie `Imię-Realm`.

- [x] **Wybór głównej postaci** — modal przy pierwszym logowaniu lub w ustawieniach; zapis do nowej kolumny `main_character` w tabeli sesji
- [ ] **Profile użytkowników** — strona `/u/{realm}/{name}` z historią symulacji, wybrana główna postać jako awatar profilu
- [ ] **Rankingi** — tabela TOP DPS per klasa/spec/fight style, generowana z publicznej historii
- [ ] **Komentarze / reakcje** — emoji-reakcje lub krótki komentarz pod wynikiem symulacji (per `job_id`)
- [ ] **Udostępnianie buildów** — eksport konfiguracji symulacji (addon text + parametry) jako publiczny link do ponownego uruchomienia
- [ ] **Porównywanie symulacji** — widok `/compare?a={job_id}&b={job_id}` z diff-em spelli i DPS obok siebie
- [ ] **Śledzenie trendów** — wykres DPS w czasie dla konkretnej postaci (endpoint `/api/history/trend` już istnieje, brakuje UI)

### Wielojęzyczność

- [x] **i18n frontend** — stringi UI wydzielone do `locales/pl.json` i `locales/en.json`; Alpine.js `$store.i18n` obsługuje reaktywne przełączanie języka
- [x] **Automatyczne wykrywanie języka** — na podstawie `navigator.language` lub ustawienia zapisanego w `localStorage`
- [x] **Angielski jako domyślny** — angielski jest domyślnym językiem; przełącznik PL/EN widoczny w headerze na każdej stronie
- [x] **Lokalizacja nazw spelli** — nazwy spelli pozostają po angielsku (SimulationCraft + WoW używają EN; gracze są do tego przyzwyczajeni)

### Techniczne

- [x] **Race condition w `simulation.py`** — `out_path` przekazywany jako argument do `_run_sim()`, nie jest czytany z `jobs[]` poza lockiem
- [x] **Gettery Alpine.js w mixa-ach** — `sortedSpells`, `filteredChars`, `pagedHistory`, `pagedNews` itp. muszą być definiowane przez `Object.defineProperties` (przez `mergeMixins`), nie przez `...spread` — spread niszczy deskryptory getterów
- [ ] **Pinowanie wersji w `requirements.txt`** — zastąpić unpinned dependencies wynikiem `pip freeze` dla reprodukowalnych buildów
- [ ] **Eksport wyników CSV** — endpoint `GET /api/result/{job_id}/csv` zwracający breakdown spelli (ma sens po dodaniu porównywania buildów)

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
│   ├── auth.py            # Battle.net OAuth2
│   ├── characters.py      # API postaci Blizzarda (lista, media, ekwipunek, statystyki, talenty)
│   ├── simulation.py      # Uruchamianie simc, kolejka jobów, watchdog
│   ├── results.py         # Parsowanie wyników JSON, generowanie wykresów PNG
│   ├── history.py         # Historia symulacji, trendy, metadane
│   ├── database.py        # Modele SQLAlchemy, migracje inline
│   ├── admin.py           # Panel admina (Keycloak), newsy, logi, limity
│   └── logging_config.py  # Strukturowane logowanie (structlog)
├── frontend/
│   ├── index.html         # Główna strona
│   ├── result.html        # Strona wyniku (OG meta, spell breakdown, chart)
│   ├── admin.html         # Panel admina
│   ├── app.js             # Logika Alpine.js (główna strona); zawiera router widoków (loadView/navigateTo)
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
│   │   └── profil.html      # Widok profilu użytkownika
│   └── locales/
│       ├── pl.json          # Tłumaczenia PL
│       └── en.json          # Tłumaczenia EN
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## Architektura frontendu

Frontend używa **Alpine.js** z wzorcem mixinów. Ważne zasady:

- `app()` jest jedynym Alpine `x-data` na stronie głównej
- Widoki (`views/*.html`) są ładowane dynamicznie przez `loadView(name)` do `#view-container` i inicjowane przez `Alpine.initTree()` — **nie mają własnego `x-data`**, działają w scope rodzica
- Mixiny (`SimMixin`, `CharsMixin`, `HistoryMixin`) są mergowane przez `mergeMixins()` która używa `Object.defineProperties` — dzięki temu gettery (np. `sortedSpells`, `filteredChars`) są poprawnie kopiowane z zachowaniem deskryptorów
- Gettery które odwołują się do `this.*` muszą być zdefiniowane bezpośrednio w obiekcie `state` w `app()`, nie w mixa-ach — przy spread `...` deskryptory getterów są tracone

## API

### Symulacja
- `POST /api/simulate` — uruchomienie symulacji
- `GET /api/job/{job_id}` — status jobu (`running` / `done` / `error`)
- `GET /api/result/{job_id}/json` — wyniki w formacie JSON
- `GET /api/result/{job_id}/dps-chart.png` — wykres DPS jako PNG
- `GET /api/result/{job_id}/meta` — metadane symulacji (postać, klasa, fight style)

### Historia
- `GET /api/history` — publiczna historia (paginacja: `?page=1&limit=50`)
- `GET /api/history/mine` — historia zalogowanego użytkownika
- `GET /api/history/trend` — historia DPS w czasie dla konkretnej postaci

### Postacie
- `GET /api/characters` — lista postaci konta (wymaga sesji)
- `GET /api/character-media` — awatar postaci
- `GET /api/character/equipment` — ekwipunek postaci
- `GET /api/character/statistics` — statystyki postaci
- `GET /api/character/talents` — talenty postaci

### Auth
- `GET /auth/login` — redirect do Battle.net OAuth
- `GET /auth/callback` — callback OAuth
- `GET /auth/logout` — wylogowanie
- `GET /auth/session/info` — info o sesji (główna postać, is_first_login)
- `PATCH /auth/session/main-character` — ustawienie głównej postaci
- `POST /auth/session/skip-first-login` — pomiń modal wyboru głównej postaci

### Admin
- `GET /admin` — panel admina (wymaga sesji Keycloak)
- `GET /admin/api/limits` — pobierz limity systemowe
- `PATCH /admin/api/limits` — aktualizuj limity systemowe
- `GET /admin/api/health` — health check usług
- `GET /admin/api/tasks` — lista aktywnych zadań
- `DELETE /admin/api/tasks/{job_id}` — anuluj zadanie

## Licencja

MIT
