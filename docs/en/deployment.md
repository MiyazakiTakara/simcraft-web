# Deployment

## Requirements

- Docker Engine 24+
- Docker Compose v2
- A domain with an A record pointing to the server
- Ports `80` and `443` open in the firewall
- Minimum 2 GB RAM (simc is memory-intensive with higher iteration counts)

---

## First Run

```bash
# 1. Clone the repo
git clone https://github.com/MiyazakiTakara/simcraft-web.git
cd simcraft-web

# 2. Copy and fill in .env
cp .env.example .env
vim .env

# 3. Build and start
docker compose up -d --build

# 4. Certbot — generate SSL certificate
docker compose exec nginx certbot --nginx -d miyazakitakara.ovh

# 5. Check logs
docker compose logs -f app
```

---

## Environment Variables (.env)

| Variable | Example | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://user:pass@db/simcraft` | PostgreSQL DSN |
| `KEYCLOAK_URL` | `https://auth.miyazakitakara.ovh` | Keycloak URL |
| `KEYCLOAK_REALM` | `simcraft` | Realm name |
| `KEYCLOAK_CLIENT_ID` | `simcraft-web` | Client ID |
| `KEYCLOAK_CLIENT_SECRET` | `secret` | Client secret |
| `ADMIN_REDIRECT_URI` | `https://miyazakitakara.ovh/admin/callback` | Admin OAuth callback |
| `APP_BASE_URL` | `https://miyazakitakara.ovh` | App base URL |
| `BLIZZARD_CLIENT_ID` | `...` | Blizzard API client ID |
| `BLIZZARD_CLIENT_SECRET` | `...` | Blizzard API secret |
| `SIMC_PATH` | `/app/SimulationCraft/simc` | Path to simc binary |
| `RESULTS_DIR` | `/app/results` | JSON results directory |
| `MAX_CONCURRENT_SIMS` | `3` | Max concurrent simulations |
| `JOB_TIMEOUT` | `360` | Simulation timeout (seconds) |

---

## Updating the Application

```bash
git pull
docker compose up -d --build app
# Verify the container started correctly
docker compose ps
docker compose logs app --tail=50
```

## Updating simc (binary)

```bash
# Enter the container
docker compose exec app bash

# Update simc (midnight branch)
cd /app/SimulationCraft
git pull origin midnight
make -j$(nproc) SC_NO_NETWORKING=1

# Check version
./simc --version
```

---

## Database Backup

```bash
# Full dump
docker compose exec db pg_dump -U simcraft simcraft > backup_$(date +%F).sql

# Restore
docker compose exec -T db psql -U simcraft simcraft < backup_2026-03-15.sql
```

---

## Certbot — Certificate Renewal

Certbot renews the certificate automatically. If manual renewal is needed:

```bash
docker compose exec nginx certbot renew
docker compose exec nginx nginx -s reload
```

---

## Monitoring & Logs

```bash
# Logs for all containers
docker compose logs -f

# App only
docker compose logs -f app

# Resource usage
docker stats

# Active simulations (via API)
curl https://miyazakitakara.ovh/admin/api/tasks -b 'admin_session=...'
```

---

## Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| `502 Bad Gateway` | App did not start | `docker compose logs app` |
| Simulation stuck on `running` | simc crash or timeout | Cancel from admin panel or `docker compose restart app` |
| `error: not found or not executable` in health | simc binary not compiled | Compile simc or check `SIMC_PATH` |
| Keycloak login loop | Wrong `ADMIN_REDIRECT_URI` | Check redirect URI in Keycloak and `.env` |
| No results after simulation | `RESULTS_DIR` not writable | `chmod 777 /app/results` or check mount |
