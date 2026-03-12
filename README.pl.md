# SimCraft Web

> 🇬🇧 [English README](./README.md)

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![Alpine.js](https://img.shields.io/badge/Alpine.js-3.x-8BC0D0?logo=alpine.js&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)

Webowy symulator DPS dla World of Warcraft oparty na SimulationCraft.

> Aplikacja jest **DPS-only** — symulacje healerów i tanków nie są obsługiwane.

## Screenshots

<!-- Dodaj screenshoty tutaj -->

## Funkcje

- **Logowanie przez Battle.net** — autoryzacja OAuth2, pobieranie postaci z armory
- **Symulacje z Armory** — automatyczne pobieranie danych postaci z API Blizzarda
- **Symulacje z Addon Export** — możliwość wklejenia tekstu z addona SimulationCraft bez logowania
- **Historia symulacji** — zapis wszystkich symulacji powiązany z kontem Battle.net (działa między przeglądarkami i sesjami); publiczna lista ostatnich wyników z paginacją
- **Wykres trendu DPS** — wykres DPS w czasie per postać i fight style w widoku profilu
- **Reakcje emoji** — 🔥💪😢💀🤣 reakcje pod wynikami symulacji; toggle/swap jak łapki YT; tylko zalogowani
- **Wykresy DPS** — wykresy kołkowe Total DMG + DPS (Plotly/kaleido, renderowane server-side do PNG)
- **Eksport CSV** — pobieranie breakdown spelli jako CSV z każdej strony wyniku
- **Social sharing** — każdy wynik ma unikalny URL z OG meta tagami (podgląd na Discordzie, Twitterze itp.)
- **Panel admina** — zarządzanie newsami, wyglądem, limitami symulacji, health check (Keycloak OAuth2)
- **Rate limiting** — ochrona przed naduzywaniem API (slowapi, per-IP)
- **Watchdog** — automatyczne czyszczenie starych jobów i obsługa timeoutów
- **Wielojęzyczność** — pełne i18n PL/EN z przełącznikiem języka, auto-detekcją z przeglądarki i zapisem w `localStorage`
- **Główna postać (main char)** — modal przy pierwszym logowaniu; zapis trwały do tabeli `users` powiązanej z `bnet_id`
- **Dropdown menu użytkownika** — rozwijane menu pod imieniem głównej postaci: Postacie, Historia, Ustawienia, Wyloguj
- **Persist widoku** — aktywny widok zapisywany w URL hash; obsługa przycisku wstecz/dalej przeglądarki

## Roadmapa

- [ ] **Profile użytkowników** — strona `/u/{realm}/{name}` z historią symulacji i awatarem głównej postaci
- [ ] **Rankingi** — tabela TOP DPS per klasa/spec/fight style
- [ ] **Udostępnianie buildów** — eksport konfiguracji symulacji jako publiczny link do ponownego uruchomienia
- [ ] **Porównywanie symulacji** — widok `/compare?a={job_id}&b={job_id}` z diff-em spelli
- [ ] **Strona ustawień** — zmiana głównej postaci, preferencje języka i motywu

## Wymagania

- Python 3.10+
- PostgreSQL 15+
- Docker & Docker Compose (zalecane)
- Konto deweloperskie Battle.net (aplikacja OAuth2)
- Keycloak (dla panelu admina)

## Uruchomienie lokalne

### Docker Compose (zalecane)

```bash
cp .env.example .env
# Edytuj .env i uzupełnij wszystkie wymagane zmienne

docker compose up --build
```

Aplikacja będzie dostępna pod adresem `http://localhost:8000`.

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

cd backend
uvicorn main:app --reload
```

## Zmienne środowiskowe

| Zmienna | Wymagana | Opis | Domyślnie |
|---------|----------|------|----------|
| `BLIZZARD_CLIENT_ID` | ✅ | ID aplikacji OAuth Battle.net | — |
| `BLIZZARD_CLIENT_SECRET` | ✅ | Secret aplikacji OAuth Battle.net | — |
| `REDIRECT_URI` | ✅ | URL powrotny po autoryzacji Battle.net | — |
| `DATABASE_URL` | ✅ | Connection string PostgreSQL | `postgresql://simcraft:simcraft@db:5432/simcraft` |
| `BASE_URL` | ✅ | Bazowy URL aplikacji (OG meta tagi, linki share) | `https://sim.miyazakitakara.ovh` |
| `KEYCLOAK_URL` | ⚠️ admin | URL Keycloak (dla panelu admina) | — |
| `KEYCLOAK_REALM` | ⚠️ admin | Realm Keycloak | — |
| `KEYCLOAK_CLIENT_ID` | ⚠️ admin | Client ID Keycloak | — |
| `KEYCLOAK_CLIENT_SECRET` | ⚠️ admin | Client Secret Keycloak | — |
| `ADMIN_REDIRECT_URI` | ⚠️ admin | URL powrotny po logowaniu admina | — |
| `RESULTS_DIR` | | Katalog na wyniki symulacji | `/app/results` |
| `SIMC_PATH` | | Ścieżka do binary simc | `/app/SimulationCraft/simc` |
| `MAX_CONCURRENT_SIMS` | | Maks. liczba równoczesnych symulacji | `3` |
| `JOB_TIMEOUT` | | Timeout symulacji w sekundach | `360` |
| `JOBS_TTL` | | Czas życia zakończonych jobów w pamięci (sekundy) | `14400` (4h) |
| `ALLOWED_ORIGINS` | | Dozwolone origins CORS (oddzielone przecinkami) | `*` |
| `LOG_LEVEL` | | Poziom logowania (`DEBUG`/`INFO`/`WARNING`/`ERROR`) | `INFO` |

## Panel admina

Panel admina dostępny pod `/admin`, wymaga sesji Keycloak.

### Co możesz konfigurować

| Sekcja | Co możesz zmienić |
|--------|-----------------|
| **Wygląd** | Emoji aplikacji, tytuł headera, tekst hero — zmiany widoczne natychmiast bez restartu |
| **Aktualności** | Dodawanie, edycja, publikowanie/ukrywanie newsów widocznych na stronie głównej |
| **Limity** | `MAX_CONCURRENT_SIMS`, `JOB_TIMEOUT`, `JOBS_TTL` — zmieniane w runtime |
| **Zadania** | Podgląd aktywnych/uruchomionych jobów, anulowanie zaciętego joba |
| **Health** | Status PostgreSQL, binary SimulationCraft, katalogu wyników |
| **Logi** | Przeglądanie ustrukturyzowanych logów aplikacji wg poziomu |

### Konfiguracja wyglądu

Wygląd jest zapisywany w `appearance.json` w katalogu wyników i udostępniany przez `GET /api/appearance` (publiczny, bez autoryzacji). Frontend pobiera go przy każdym załadowaniu strony.

Przykładowy `appearance.json`:
```json
{
  "emoji": "⚔️",
  "header_title": "SimCraft Web",
  "hero_title": "WoW DPS Simulator"
}
```

## Wielojęzyczność (i18n)

Aplikacja obsługuje wiele języków przez pliki `frontend/locales/*.json` i store Alpine.js `$store.i18n`.

### Jak dodać nowy język

1. Skopiuj `frontend/locales/en.json` jako np. `frontend/locales/de.json`
2. Przetłumacz wszystkie wartości (klucze muszą pozostać bez zmian)
3. W `frontend/i18n.js` dodaj `'de'` do tablicy `SUPPORTED_LANGS`
4. Dodaj przycisk przełącznika języka w `index.html` i `result.html`

### Używanie tłumaczeń w HTML

```html
<!-- Prosty klucz -->
<span x-text="$store.i18n.t('header.profile')"></span>

<!-- Klucz z interpolacją -->
<span x-text="$store.i18n.t('header.characters_count', { count: 5 })"></span>
```

### Struktura plików tłumaczeń

Główne klucze: `meta`, `header`, `nav`, `lang`, `common`, `home`, `sim`, `result`, `chars`, `history`, `news`, `profile`, `errors`.

## Architektura

```
Przeglądarka
  │
  ├── Alpine.js (frontend) ─────────────────────────────┐
  │   Widoki: home / symulacje / profil / ustawienia    │
  │   Miksyny: SimMixin, CharsMixin, HistoryMixin        │
  └─────────────────────────────────────────────────┘
          │ HTTP (REST)
  ┌───────┴───────┐
  │  FastAPI backend  │
  │  (Python 3.10+)   │
  │                   │
  │  auth.py          │───► Battle.net OAuth2
  │  characters.py    │───► Blizzard API (armory)
  │  simulation.py    │───► simc binary (subprocess)
  │  results.py       │───► Plotly/kaleido (wykresy PNG)
  │  history.py       │┐
  │  reactions.py     ││
  │  admin.py         ││─► PostgreSQL (SQLAlchemy)
  │  database.py      │┘          tabele: users, sessions,
  └─────────────────┘          history, jobs, reactions,
                                   news, admin_logs
```

## Struktura projektu

```
simcraft-web/
├── backend/
│   ├── main.py            # FastAPI app, routing, OG meta, startup
│   ├── auth.py            # Battle.net OAuth2; pobiera bnet_id z /userinfo
│   ├── characters.py      # API postaci Blizzarda (lista, media, ekwipunek, stat, talenty)
│   ├── simulation.py      # Uruchamianie simc, kolejka jobów, watchdog
│   ├── results.py         # Parsowanie wyników JSON, generowanie wykresów PNG
│   ├── history.py         # Historia symulacji (powiązana z bnet_id), trendy, metadane
│   ├── reactions.py       # Reakcje emoji (GET/POST), logika toggle/swap
│   ├── database.py        # Modele SQLAlchemy + migracje inline
│   ├── admin.py           # Panel admina (Keycloak), newsy, logi, limity, wygląd
│   └── logging_config.py  # Strukturowane logowanie (structlog)
├── frontend/
│   ├── index.html         # Główna powłoka SPA
│   ├── result.html        # Strona wyniku (OG meta, spell breakdown, wykres, reakcje)
│   ├── admin.html         # Panel admina
│   ├── app.js             # Alpine.js root; router widoków
│   ├── sim.js             # Logika formularza symulacji (SimMixin)
│   ├── chars.js           # Lista postaci, ekwipunek, talenty (CharsMixin)
│   ├── history.js         # Widget historii (HistoryMixin)
│   ├── api.js             # API client (fetch wrapper)
│   ├── utils.js           # Helpers
│   ├── admin.js           # Logika panelu admina
│   ├── i18n.js            # System tłumaczeń (Alpine store, auto-detect, localStorage)
│   ├── style.css          # Style globalne (dark theme)
│   ├── views/
│   │   ├── home.html        # Widok strony głównej
│   │   ├── symulacje.html   # Widok symulacji
│   │   ├── profil.html      # Widok profilu (postaci, historia, trend DPS)
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
- Widoki (`views/*.html`) są ładowane dynamicznie przez `loadView(name)` do `#view-container` i inicjowane przez `Alpine.initTree()` — **nie mają własnego `x-data`**
- Miksyny są mergowane przez `mergeMixins()` z `Object.defineProperties` — zachowuje deskryptory getterów
- Poprawne trasy hash: `#symulacje`, `#profil`, `#ustawienia`

## API

### Symulacja
| Metoda | Endpoint | Opis |
|--------|----------|------|
| `POST` | `/api/simulate` | Uruchomienie symulacji |
| `GET` | `/api/job/{job_id}` | Status jobu (`running` / `done` / `error`) |
| `GET` | `/api/result/{job_id}/json` | Wyniki w formacie JSON |
| `GET` | `/api/result/{job_id}/dps-chart.png` | Wykres DPS jako PNG |
| `GET` | `/api/result/{job_id}/meta` | Metadane symulacji |
| `GET` | `/api/result/{job_id}/csv` | Breakdown spelli jako CSV |

### Historia
| Metoda | Endpoint | Opis |
|--------|----------|------|
| `GET` | `/api/history` | Publiczna historia (paginacja: `?page=1&limit=50`) |
| `GET` | `/api/history/mine` | Historia zalogowanego użytkownika |
| `GET` | `/api/history/trend` | Historia DPS w czasie dla konkretnej postaci |

### Reakcje
| Metoda | Endpoint | Opis |
|--------|----------|------|
| `GET` | `/api/reactions/{job_id}` | Liczniki reakcji + moja reakcja (`?session=...`) |
| `POST` | `/api/reactions/{job_id}` | Ustaw/zmień/usuń reakcję (toggle = ta sama usuwa) |

### Postacie
| Metoda | Endpoint | Opis |
|--------|----------|------|
| `GET` | `/api/characters` | Lista postaci konta (wymaga sesji) |
| `GET` | `/api/character-media` | Awatar postaci |
| `GET` | `/api/character/equipment` | Ekwipunek postaci |
| `GET` | `/api/character/statistics` | Statystyki postaci |
| `GET` | `/api/character/talents` | Talenty postaci |

### Auth
| Metoda | Endpoint | Opis |
|--------|----------|------|
| `GET` | `/auth/login` | Redirect do Battle.net OAuth |
| `GET` | `/auth/callback` | Callback OAuth |
| `GET` | `/auth/logout` | Wylogowanie |
| `GET` | `/auth/session/info` | Info o sesji |
| `PATCH` | `/auth/session/main-character` | Ustawienie głównej postaci |
| `POST` | `/auth/session/skip-first-login` | Pomij modal wyboru postaci |

### Admin
| Metoda | Endpoint | Opis |
|--------|----------|------|
| `GET` | `/admin` | Panel admina (wymaga Keycloak) |
| `GET` | `/admin/api/limits` | Pobierz limity systemowe |
| `PATCH` | `/admin/api/limits` | Aktualizuj limity |
| `GET` | `/admin/api/health` | Health check usług |
| `GET` | `/admin/api/tasks` | Lista aktywnych zadań |
| `DELETE` | `/admin/api/tasks/{job_id}` | Anuluj zadanie |
| `GET` | `/api/appearance` | Pobierz konfig wyglądu (publiczny) |
| `PATCH` | `/admin/api/appearance` | Aktualizuj konfig wyglądu |

## Schemat bazy danych

| Tabela | Opis |
|--------|------|
| `users` | Konta Battle.net; przechowuje `bnet_id`, główna postać |
| `sessions` | Aktywne sesje OAuth; przechowuje `bnet_id`, token, expiry |
| `history` | Wszystkie wyniki symulacji; powiązane z `bnet_id` lub gość |
| `jobs` | Kolejka jobów symulacji; śledzenie statusu |
| `reactions` | Reakcje emoji per `job_id`; `UNIQUE(job_id, user_key)` |
| `news` | Aktualności zarządzane z panelu admina |
| `admin_logs` | Ustrukturyzowane logi aplikacji |
| `admin_sessions` | Sesje admina Keycloak |

> Migracje są aplikowane automatycznie przez `init_db()` przy starcie przez `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` — bez narzędzi migracyjnych.

## Licencja

MIT
