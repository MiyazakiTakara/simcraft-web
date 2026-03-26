# Instrukcja obsługi panelu admina

Panel admina dostępny jest pod adresem `/admin`.
Logowanie odbywa się przez Keycloak — konto musi mieć rolę `admin` w realmie.

---

## Logowanie i sesja

1. Wejdź na `/admin` — zostaniesz przekierowany do Keycloak
2. Zaloguj się kontem z rolą admina
3. Sesja wygasa po **8 godzinach** — po wygaśnięciu zostaniesz przekierowany do logowania
4. Wylogowanie przez przycisk **Wyloguj** w prawym górnym rogu

---

## Zakładki

### 📊 Dashboard
Główna strona z kluczowymi statystykami. Odświeża się automatycznie co **30 sekund**.

- Łączna liczba symulacji (dziś / tydzień / miesiąc)
- Aktywne zadania i zużycie CPU/RAM
- Uptime serwera
- Wykres trendu symulacji (30 dni)
- Rozkład klas i fight style'ów
- Top 10 DPS globalnie (klikalny job_id → `/result/{id}`)

---

### 📈 Ruch
Analityka ruchu na stronie. Odświeża się co **60 sekund**.

- Wizyty dziś / 7 dni / 30 dni, unikalni użytkownicy (na podstawie IP hash)
- Wykres dzienny — total vs unique visitors (30 dni)
- Heatmapa godzinowa ruchu (ostatnie 7 dni)
- Top 10 najczęściej odwiedzanych podstron (30 dni)

---

### 📰 News
Zarządzanie newsami wyświetlanymi na stronie głównej.

- **Dodawanie** — tytuł + treść (plain text lub Markdown) + checkbox publikacji
- **Edycja** — kliknij wpis, zmodyfikuj, zapisz
- **Usuwanie** — przycisk `×` przy wpisie
- **Publikacja** — toggle "opublikowany" — niepublikowane newsy nie są widoczne dla użytkowników

---

### 👥 Użytkownicy
Lista aktywnych użytkowników z podstawowymi statystykami.

| Kolumna | Opis |
|---------|------|
| Postac | Nazwa + klasa + spec z ostatniej symulacji |
| Symulacje | Łączna liczba |
| Avg DPS | Średnia DPS ze wszystkich symulacji |
| Ostatnia aktywność | Data ostatniej symulacji |

Kliknięcie na użytkownika otwiera modal z listą jego ostatnich 20 symulacji.

> ⚠️ Lista pokazuje tylko użytkowników którzy wykonali przynajmniej jedną symulację.

---

### 📋 Logi
Logi aplikacji w czasie rzeczywistym. Odświeża się automatycznie co **15 sekund**.

- Filtrowanie po poziomie: `INFO`, `WARNING`, `ERROR`
- Kolor poziomów: INFO — szary, WARNING — żółty, ERROR — czerwony
- Logi z frontendu (błędy JS) są raportowane przez endpoint `/admin/api/client-error`

---

### ⚙️ Limity
Konfiguracja limitów systemowych.

| Ustawienie | Domyślnie | Opis |
|-----------|-----------|------|
| Max jednoczesnych symulacji | 3 | Ile simc może działać równocześnie |
| Rate limit / min | 5 | Max symulacji na minutę per user |
| Timeout symulacji | 360s | Po ilu sekundach simc zostanie zabity |

> ⚠️ Zmiany limitów są tymczasowe — nie są zapisywane do pliku. Aby utrwalić zmień zmienne środowiskowe w `.env` i zrestartuj kontener.

---

### 🏥 Health
Status wszystkich serwisów. Odświeża się co **60 sekund**.

| Serwis | Co sprawdza |
|--------|-------------|
| Database | `SELECT 1` na PostgreSQL |
| Blizzard API | Pobranie tokenu OAuth |
| Keycloak | `/.well-known/openid-configuration` |
| simc binary | Istnienie i uprawnienia wykonania |
| Results dir | Istnienie i zapisywalność katalogu wyników |
| simc version | Porównanie lokalnej wersji z najnowszą na GitHub (cache 1h) |

---

### 🔧 Zadania
Aktywne symulacje w toku. Odświeża się co **10 sekund**.

- Lista job_id + czas startu
- Przycisk **Anuluj** — natychmiastowe zakończenie zadania (status: `error`, reason: `Cancelled by admin`)

---

### 🎨 Wygląd
Customizacja UI bez redeploy.

- **Tytuł w headerze** — tekst obok emoji w nawigacji
- **Tytuł hero** — tytuł na stronie głównej (np. `World of Warcraft`)
- **Własny tekst hero** — jeśli wypełniony, zastępuje cały domyślny blok hero
- **Emoji** — wybierz z palety lub wpisz ręcznie

Zmiany są zapisywane do `config/appearance.json` i wchodzą w życie natychmiast.

---

### 📚 Dokumentacja
Przeglądarka plików `.md` z katalogu `docs/`.

- Kliknij plik w lewym sidebarze — treść renderuje się z Markdown do HTML
- Syntax highlighting dla bloków kodu (motyw `github-dark`)
- Przycisk **Kopiuj Markdown** — kopiuje surowy `.md` do schowka
- Switcher języka w sidebarze (PL / EN)
- Pliki są cachowane w pamięci podczas sesji — odśwież stronę jeśli zmieniłeś plik

---

## Bezpieczeństwo

- Sesja admina wygasa po **8 godzinach**
- Dostęp wymaga konta w Keycloak
- Panel należy docelowo przenieść na subdomenę z IP allowlist (patrz issue #45)
- Logi błędów JS są rate-limitowane — max 10 req/min per IP (endpoint `/admin/api/client-error`)
