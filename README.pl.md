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
- **Great Vault Finder** — strona `/vault`; wklej addon export (z otwartym Great Vault w grze), auto-wykrywa przedmioty, symuluje każdy jako upgrade i sortuje wg zysku DPS
- **Historia symulacji** — zapis wszystkich symulacji powiązany z kontem Battle.net (działa między przeglądarkami i sesjami); publiczna lista ostatnich wyników z paginacją
- **Wykres trendu DPS** — wykres DPS w czasie per postać i fight style w widoku profilu
- **Reakcje emoji** — 🔥💪😢💀🤣 reakcje pod wynikami symulacji; toggle/swap jak łapki YT; tylko zalogowani
- **Wykresy DPS** — wykresy kołowe Total DMG + DPS (Plotly/kaleido, renderowane server-side do PNG)
- **Eksport CSV** — pobieranie breakdown spelli jako CSV z każdej strony wyniku
- **Social sharing** — każdy wynik ma unikalny URL z OG meta tagami (podgląd na Discordzie, Twitterze itp.)
- **Rankingi** — strona `/rankings` z podium TOP DPS (🥇🥈🥉) + tabela miejsc 4–10; filtry po fight style, klasie, specu; jedna postać raz; mini-podium top 3 na stronie głównej
- **Ulepszenia strony wyniku** — badge ze średnim item level; lista założonego ekwipunku ze slotem, ilvl, ikoną, linkiem Wowhead; paski uptime buffów; link do profilu autora (`/u/{bnet_id}`); string talentów z kopiowaniem jednym kliknięciem
- **Panel admina** — zarządzanie newsami, wyglądem, limitami symulacji, health check, lista jobów, lista użytkowników, logi (Keycloak OAuth2)
- **Śledzenie błędów admina** — handler `window.onerror` i `unhandledrejection` w `admin/core.js`; błędy wysyłane do `POST /admin/api/client-error`; rate limiting per-IP (10 req/min); zapisywane w tabeli `admin_logs`; widoczne w zakładce Logi
- **Rate limiting** — ochrona przed naduzywaniem API (slowapi, per-IP)
- **Watchdog** — automatyczne czyszczenie starych jobów i obsługa timeoutów
- **Wielojęzyczność** — pełne i18n PL/EN z przełącznikiem języka, auto-detekcją z przeglądarki i zapisem w `localStorage`
- **Główna postać** — modal przy pierwszym logowaniu do wyboru głównej postaci; zapis trwały do konta Battle.net (tabela `users`); wyświetlana w dropdownie headera
- **Dropdown menu użytkownika** — rozwijane menu pod imieniem głównej postaci: Postacie, Historia, Publiczny profil, Ulubione, Ustawienia, Wyloguj
- **Persist widoku** — aktywny widok (home/symulacje/profil/ustawienia/ulubione) zapisywany w URL hash; obsługa przycisku wstecz/dalej przeglądarki
- **Strona ustawień** — zmiana głównej postaci (z listy postaci), język, motyw; przełącznik prywatności profilu; prywatność per postać
- **Sliding session** — TTL sesji przedłużany o 30 dni przy każdym aktywnym użyciu; brak wymuszonych ponownych logowań
- **Skeleton loadery** — szkielety ładowania w widokach home, symulacje, profil zamiast spinnerów
- **Smart history loading** — home zawsze ładuje publiczną historię; `/symulacje` i `/profil` ładują prywatną dla zalogowanych, publiczną dla gości; historia przeładowuje się przy każdej zmianie widoku
- **Design Tokens** — CSS custom properties dla wszystkich kolorów (w tym `--danger` z wariantami dark/light), spacings, typografii, promieni, cieni
- **Publiczne profile** — każdy użytkownik Battle.net ma publiczny profil pod `/u/{bnet_id}` z główną postacią, najlepszym DPS, liczbą symulacji i historią; respektuje ustawienia prywatności
- **Ulubione** — zalogowani użytkownicy mogą dodawać profile do ulubionych (przycisk ❤️ na stronie profilu); powiązane z `bnet_id`, dostępne na wszystkich urządzeniach; widok `/#ulubione`
- **Breakdown spelli z ikonami** — ikony spelli z WoW CDN przy każdej zdolności; tooltip Wowhead po najechaniu (natywny widget, `tooltips.js`); działa na `#symulacje` i `/result/`
- **Log sekwencji akcji** — związana oś czasu wszystkich eventów w przykładowej iteracji (cast / proc / buff / debuff), z ikonami spelli
- **Paski uptime buffów** — paski postępu dla buffów i debuffów z częściowym uptime (0–100%); kolorowane wg typu
- **Liczniki reakcji w historii profilu** — podsumowanie reakcji emoji (🔥 3 💀 1) przy każdym wpisie historii w widoku profilu; backend agreguje z tabeli `reactions` przez `LEFT JOIN`
- **Admin: widoczni wszyscy zarejestrowani użytkownicy** — lista użytkowników używa `LEFT JOIN`, użytkownicy z 0 symulacjami są widoczni z `sim_count: 0`

## Roadmapa

### 🤷 Może kiedyś
- [ ] **Admin: wyróŻnione/przypite wyniki** — admin może wyrozłnić konkretną symulację (np. tygodniowy rekord DPS) z niestandardową etykietą; przypite wyniki pojawiają się w dedykowanej sekcji na stronie głównej; maks. 3–5 na raz ([#69](https://github.com/MiyazakiTakara/simcraft-web/issues/69))
- [ ] **Admin: zarządzanie rolami** — nadawanie/odbieranie roli `admin` bezpośrednio z panelu bez wchodzenia do konsoli Keycloak; wymaga konta serwisowego Keycloak z uprawnieniami `manage-users` ([#65](https://github.com/MiyazakiTakara/simcraft-web/issues/65))
- [ ] **Auth: ujednolicone logowanie** — połączenie konta admina Keycloak z kontem Battle.net dla jednego flow logowania; odrzucone na razie — konta adminowe to SSO-only, bez overlapa z BNet ([#57](https://github.com/MiyazakiTakara/simcraft-web/issues/57))

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
| **Użytkownicy** | Przeglądanie zarejestrowanych użytkowników (wszyscy, nie tylko z symulacjami) |
| **Logi** | Przeglądanie ustrukturyzowanych logów aplikacji wg poziomu (INFO/WARNING/ERROR); w tym błędy JS z frontendu |

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

```
locales/
  pl.json   — Polski (domyślny)
  en.json   — Angielski
```

Główne klucze: `meta`, `header`, `nav`, `lang`, `common`, `home`, `sim`, `result`, `chars`, `history`, `news`, `rankings`, `profile`, `following`, `settings`, `gdpr`, `info`, `errors`, `vault`, `admin`.

## Architektura

```
Przeglądarka
  │
  ├── Alpine.js (frontend) ──────────────────────────────┐
  │   Widoki: home / symulacje / profil / ustawienia / ulubione  │
  │   Miksyny: SimMixin, CharsMixin, HistoryMixin                 │
  └───────────────────────────────────────────────────┘
          │ HTTP (REST)
  ┌───────┴───────┐
  │  FastAPI backend  │
  │  (Python 3.10+)   │
  │                   │
  │  auth.py          │───► Battle.net OAuth2
  │  characters.py    │───► Blizzard API (armory)
  │  simulation.py    │───► simc binary (subprocess)
  │  results.py       │───► Plotly/kaleido (wykresy PNG)
  │  history.py       │┌
  │  reactions.py     ││
  │  rankings.py      ││
  │  profiles.py      ││
  │  favorites.py     ││─► PostgreSQL (SQLAlchemy)
  │  vault.py         ││          tabele: users, sessions,
  │  admin.py         ││          simulations, reactions,
  │  database.py      │┘          news, admin_logs, favorites
  └─────────────────┘
```

## Struktura projektu

```
simcraft-web/
├── backend/
│   ├── main.py            # FastAPI app, routing, OG meta, startup
│   ├── auth.py            # Battle.net OAuth2; pobiera bnet_id z /userinfo
│   ├── characters.py      # API postaci Blizzarda (lista, media, ekwipunek, stat, talenty)
│   ├── simulation.py      # Uruchamianie simc, kolejka jobów, watchdog
│   ├── results.py         # Parsowanie wyników JSON, generowanie wykresów PNG (Plotly/kaleido)
│   ├── history.py         # Historia symulacji (powiązana z bnet_id), trendy, metadane
│   ├── reactions.py       # Reakcje emoji (GET/POST), logika toggle/swap
│   ├── rankings.py        # Rankings API (top 10, top 3 podium, meta)
│   ├── profiles.py        # Publiczne profile użytkowników GET /api/profile/{bnet_id}
│   ├── favorites.py       # System ulubionych (add/remove/list/check); ensure_table() przy starcie
│   ├── vault.py           # Grupowa symulacja Great Vault; /api/vault/start + /api/vault/status/{group_id}
│   ├── database.py        # Modele SQLAlchemy + migracje inline
│   ├── admin.py           # Panel admina (Keycloak), newsy, logi, limity, wygląd, client-error
│   └── logging_config.py  # Strukturowane logowanie (structlog)
├── frontend/
│   ├── index.html         # Główna powłoka SPA
│   ├── result.html        # Strona wyniku (OG meta, spell breakdown, wykres, reakcje)
│   ├── rankings.html      # Strona rankingów (podium + tabela, filtry)
│   ├── profile.html       # Publiczny profil użytkownika (/u/{bnet_id})
│   ├── vault.html         # Strona Great Vault Finder (/vault)
│   ├── admin.html         # Panel admina
│   ├── app.js             # Alpine.js root; router widoków (loadView/navigateTo/handleHash)
│   ├── sim.js             # Logika formularza symulacji (SimMixin)
│   ├── chars.js           # Lista postaci, ekwipunek, talenty (CharsMixin)
│   ├── history.js         # Widget historii (HistoryMixin)
│   ├── settings.js        # Mixin ustawień (główna postać, prywatność, motyw, język)
│   ├── favorites.js       # Komponent Alpine favoritesView() dla /#ulubione
│   ├── header.js          # Mixin headera (sesja, dropdown)
│   ├── api.js             # API client (fetch wrapper)
│   ├── utils.js           # Helpery (formatowanie liczb, kolory klas itp.)
│   ├── vault.js           # Komponent Alpine vaultPage(); parseSimcItemLine(); logika pollingu
│   ├── result-panel.js    # Komponent Alpine ResultPanel(); spell breakdown, ekwipunek, buffy, talenty, reakcje
│   ├── admin/
│   │   └── core.js        # JS panelu admina; globalny handler błędów (window.onerror + unhandledrejection)
│   ├── i18n.js            # System tłumaczeń (Alpine store, auto-detect, localStorage)
│   ├── style.css          # Style globalne (design tokens, dark/light theme, komponenty)
│   ├── views/
│   │   ├── home.html        # Widok strony głównej (hero, formularz addon, podium top 3, historia publiczna, newsy)
│   │   ├── symulacje.html   # Widok symulacji (lista postaci, formularz, wyniki, historia)
│   │   ├── profil.html      # Widok profilu (postacie, historia, wykres trendu DPS)
│   │   ├── ulubione.html    # Widok ulubionych (siatka ulubionych profilów)
│   │   └── ustawienia.html  # Widok ustawień (wybór głównej postaci, prywatność, motyw, język)
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
- Widoki (`views/*.html`) są ładowane dynamicznie przez `loadView(name)` do `#view-container` i inicjowane przez `Alpine.initTree()` — **nie mają własnego `x-data`**, działają w ramach zakresu rodzica
- **Wyjątek:** widoki wymagające izolowanego stanu (np. `ulubione.html`) używają `x-data="favoritesView()"`, ale funkcja **musi być zdefiniowana globalnie** (w `<script>` załadowanym w `index.html`) przed bootem Alpine — inline `<script>` wewnątrz `innerHTML` nie jest wykonywany przez przeglądarkę
- Miksyny (`SimMixin`, `CharsMixin`, `HistoryMixin`) są mergowane przez `mergeMixins()` z `Object.defineProperties` — zapewnia to prawidłowe kopiowanie getterów (np. `sortedSpells`, `filteredChars`) z zachowaniem deskryptorów
- Gettery odwołujące się do `this.*` muszą być zdefiniowane bezpośrednio w obiekcie `state` w `app()`, nie w miksynach — `...spread` niszczy deskryptory getterów
- Poprawne trasy hash: `#symulacje`, `#profil`, `#ustawienia`, `#ulubione`
- `rankings.html`, `profile.html` i `vault.html` to **osobne strony** (nie widoki), serwowane przez FastAPI pod `GET /rankings`, `GET /u/{bnet_id}` i `GET /vault`
- **Nazwy właściwości stanu mają znaczenie** — widoki używają rzeczywistych nazw pól stanu (np. `loadingHistory`, nie aliasy)
- **Tooltips Wowhead** — `tooltips.js` załadowany w `index.html` i `result.html`; `whTooltips = {colorLinks:false, iconizeLinks:false, renameLinks:false}`; na `/result/` `WH.Tooltips.refreshLinks()` wywoływane po wyrenderowaniu linków przez Alpine (`await $nextTick()`)

## Design Tokens (CSS)

Wszystkie stałe wizualne są zdefiniowane jako CSS custom properties w `:root` i nadpisywane w `[data-theme="light"]`:

| Token | Ciemny | Jasny | Zastosowanie |
|-------|--------|-------|-------------|
| `--accent` | `#c89a3c` | `#a07820` | Główny kolor marki, aktywne zakładki, przyciski CTA |
| `--accent2` | `#7c5cfc` | `#5a3fd4` | Drugi akcent, przyciski publicznych postaci |
| `--danger` | `#c0392b` | `#e74c3c` | Akcje destrukcyjne, prywatne postacie, aktywne przyciski segmentu |
| `--bg` | `#0d0e12` | `#f4f5f7` | Tło strony |
| `--surface` | `#1a1b22` | `#ffffff` | Tło kart/panelów |
| `--border` | `#2e3040` | `#d0d4e0` | Obramowania, separatory |
| `--text` | `#e8e8f0` | `#1a1b22` | Tekst główny |
| `--muted` | `#8888aa` | `#666688` | Tekst drugorzedny, etykiety |

## API

### Symulacja
| Metoda | Endpoint | Opis |
|--------|----------|------|
| `POST` | `/api/simulate` | Uruchomienie symulacji |
| `GET` | `/api/job/{job_id}` | Status jobu (`running` / `done` / `error`) |
| `GET` | `/api/result/{job_id}/json` | Wyniki w formacie JSON |
| `GET` | `/api/result/{job_id}/dps-chart.png` | Wykres DPS jako PNG |
| `GET` | `/api/result/{job_id}/meta` | Metadane symulacji (postać, klasa, fight style, autor, talenty, item level) |
| `GET` | `/api/result/{job_id}/csv` | Breakdown spelli jako CSV |
| `GET` | `/api/icon-by-spell/{spell_id}` | Redirect do ikony spella na WoW CDN |
| `GET` | `/api/spell-tooltip/{spell_id}` | Dane tooltipa spella (nazwa, opis, ikona, czas rzucania itp.) |

### Great Vault
| Metoda | Endpoint | Opis |
|--------|----------|------|
| `POST` | `/api/vault/start` | Uruchomienie grupowej symulacji Great Vault (baseline + jedna symulacja na przedmiot) |
| `GET` | `/api/vault/status/{group_id}` | Status grupy; zwraca `done_count`, `total`, `baseline_dps`, posortowane `results` |

### Historia
| Metoda | Endpoint | Opis |
|--------|----------|------|
| `GET` | `/api/history` | Publiczna historia (paginacja: `?page=1&limit=50`) |
| `GET` | `/api/history/mine` | Historia zalogowanego użytkownika (filtrowana po `bnet_id`) |
| `GET` | `/api/history/trend` | DPS w czasie dla konkretnej postaci (`?name=...&fight_style=...`) |

### Rankingi
| Metoda | Endpoint | Opis |
|--------|----------|------|
| `GET` | `/api/rankings` | Top 10 per fight style/klasa/spec; jedna postać raz (`?fight_style=&character_class=&character_spec=&limit=10`) |
| `GET` | `/api/rankings/top3` | Top 3 dla podium na stronie głównej (`?fight_style=Patchwerk`) |
| `GET` | `/api/rankings/meta` | Dostępne klasy, spece, fight styles dla dropdownów filtrów |

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

### Profile
| Metoda | Endpoint | Opis |
|--------|----------|------|
| `GET` | `/api/profile/{bnet_id}` | Publiczny profil (główna postać, najlepszy DPS, liczba symulacji, historia); 404 jeśli prywatny |

### Ulubione
| Metoda | Endpoint | Opis |
|--------|----------|------|
| `GET` | `/api/favorites` | Lista ulubionych profilów zalogowanego użytkownika (`?session=...`) |
| `POST` | `/api/favorites/{bnet_id}` | Dodaj profil do ulubionych (`?session=...`) |
| `DELETE` | `/api/favorites/{bnet_id}` | Usuń profil z ulubionych (`?session=...`) |
| `GET` | `/api/favorites/check/{bnet_id}` | Sprawdź czy profil jest w ulubionych (`?session=...`) |

### Auth
| Metoda | Endpoint | Opis |
|--------|----------|------|
| `GET` | `/auth/login` | Redirect do Battle.net OAuth |
| `GET` | `/auth/callback` | Callback OAuth (pobiera `bnet_id` z `/userinfo`) |
| `GET` | `/auth/logout` | Wylogowanie |
| `GET` | `/auth/session/info` | Info o sesji (główna postać, bnet_id, is_first_login) |
| `GET` | `/auth/session/settings` | Pobierz ustawienia użytkownika (główna postać, prywatność) |
| `PATCH` | `/auth/session/settings` | Zapisz ustawienia użytkownika |
| `PATCH` | `/auth/session/main-character` | Ustaw główną postać |
| `POST` | `/auth/session/skip-first-login` | Pomiń modal wyboru postaci |

### Admin
| Metoda | Endpoint | Opis |
|--------|----------|------|
| `GET` | `/admin` | Panel admina (wymaga sesji Keycloak) |
| `GET` | `/admin/api/limits` | Pobierz limity systemowe |
| `PATCH` | `/admin/api/limits` | Aktualizuj limity |
| `GET` | `/admin/api/health` | Health check usług |
| `GET` | `/admin/api/tasks` | Lista aktywnych zadań |
| `DELETE` | `/admin/api/tasks/{job_id}` | Anuluj zadanie |
| `GET` | `/admin/api/users` | Lista wszystkich zarejestrowanych użytkowników z liczbą symulacji |
| `GET` | `/api/appearance` | Pobierz konfig wyglądu (publiczny) |
| `PATCH` | `/admin/api/appearance` | Aktualizuj konfig wyglądu |
| `POST` | `/admin/api/client-error` | Odbierz błędy JS z frontendu (rate-limited: 10 req/min per IP) |

## Schemat bazy danych

| Tabela | Opis |
|--------|------|
| `users` | Konta Battle.net; przechowuje `bnet_id`, główną postać, ustawienia prywatności |
| `sessions` | Aktywne sesje OAuth; sliding 30-dniowy TTL przedłużany przy każdym aktywnym użyciu |
| `simulations` | Wszystkie wyniki symulacji; powiązane z `bnet_id` lub gość; przechowuje `simc_input`, `dps`, `character_*`, `fight_style`, `created_at` |
| `jobs` | Kolejka jobów symulacji; śledzenie statusu |
| `reactions` | Reakcje emoji per `job_id`; `UNIQUE(job_id, user_key)` |
| `news` | Aktualności zarządzane z panelu admina |
| `admin_logs` | Ustrukturyzowane logi aplikacji; zawiera błędy JS z frontendu z `/admin/api/client-error` |
| `admin_sessions` | Sesje admina Keycloak |
| `favorites` | Ulubione profile; `UNIQUE(user_bnet_id, target_bnet_id)`; tworzone przez `ensure_table()` przy starcie |

> Migracje są aplikowane automatycznie przez `init_db()` przy starcie przez `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` — bez narzędzi migracyjnych.

## Licencja

MIT
