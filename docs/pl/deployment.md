# Deployment

## Wymagania

- Docker Engine 24+
- Docker Compose v2
- Domena z rekordem A wskazującym na serwer
- Porty `80` i `443` otwarte w firewallu
- Minimum 2GB RAM

---

## Pierwsze uruchomienie

```bash
# 1. Sklonuj repo
git clone https://github.com/MiyazakiTakara/simcraft-web.git
cd simcraft-web

# 2. Skopiuj i uzupełnij .env
cp .env.example .env
vim .env

# 3. Zbuduj i uruchom
docker compose up -d --build

# 4. Certbot — SSL
docker compose exec nginx certbot --nginx -d miyazakitakara.ovh

# 5. Sprawdź logi
docker compose logs -f app
```

---

## Zmienne środowiskowe (.env)

| Zmienna | Przykład | Opis |
|---------|---------|------|
| `DATABASE_URL` | `postgresql://user:pass@db/simcraft` | PostgreSQL DSN |
| `KEYCLOAK_URL` | `https://auth.miyazakitakara.ovh` | URL Keycloak |
| `KEYCLOAK_REALM` | `simcraft` | Nazwa realmu |
| `KEYCLOAK_CLIENT_ID` | `simcraft-web` | Client ID |
| `KEYCLOAK_CLIENT_SECRET` | `secret` | Client secret |
| `ADMIN_REDIRECT_URI` | `https://miyazakitakara.ovh/admin/callback` | OAuth callback |
| `APP_BASE_URL` | `https://miyazakitakara.ovh` | Bazowy URL |
| `BLIZZARD_CLIENT_ID` | `...` | Blizzard API client ID |
| `BLIZZARD_CLIENT_SECRET` | `...` | Blizzard API secret |
| `SIMC_PATH` | `/app/SimulationCraft/simc` | Ścieżka do simc |
| `RESULTS_DIR` | `/app/results` | Katalog wyników JSON |
| `MAX_CONCURRENT_SIMS` | `3` | Maks. równoległych symulacji |
| `JOB_TIMEOUT` | `360` | Timeout symulacji (s) |

---

## Aktualizacja aplikacji

```bash
git pull
docker compose up -d --build app
docker compose ps
docker compose logs app --tail=50
```

## Aktualizacja simc (binary)

```bash
docker compose exec app bash
cd /app/SimulationCraft
git pull origin midnight
make -j$(nproc) SC_NO_NETWORKING=1
./simc --version
```

---

## Backup bazy danych

```bash
# Pełny dump
docker compose exec db pg_dump -U simcraft simcraft > backup_$(date +%F).sql

# Przywracanie
docker compose exec -T db psql -U simcraft simcraft < backup_2026-03-15.sql
```

---

## Certbot — odnawianie

```bash
docker compose exec nginx certbot renew
docker compose exec nginx nginx -s reload
```

---

## Troubleshooting

| Problem | Przyczyna | Rozwiązanie |
|---------|-----------|-------------|
| `502 Bad Gateway` | App nie wystartowała | `docker compose logs app` |
| Symulacja wisi na `running` | simc crash lub timeout | Anuluj z panelu lub `docker compose restart app` |
| `error: not found or not executable` | simc nie skompilowany | Skompiluj simc lub sprawdź `SIMC_PATH` |
| Login loop Keycloak | Zły `ADMIN_REDIRECT_URI` | Sprawdź redirect URI w Keycloak i `.env` |
| Brak wyników | `RESULTS_DIR` nie zapisywalny | `chmod 777 /app/results` |
