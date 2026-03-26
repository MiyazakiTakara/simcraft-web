# Admin Panel Guide

The admin panel is available at `/admin`.
Login is handled by Keycloak — your account must have the `admin` role in the realm.

---

## Login & Session

1. Go to `/admin` — you will be redirected to Keycloak
2. Log in with an account that has the admin role
3. Session expires after **8 hours** — you will be redirected to the login page on expiry
4. Log out via the **Logout** button in the top-right corner

---

## Tabs

### 📊 Dashboard
Main page with key statistics. Auto-refreshes every **30 seconds**.

- Total simulations (today / this week / this month)
- Active tasks and CPU/RAM usage
- Server uptime
- Simulation trend chart (30 days)
- Class and fight style distribution
- Global Top 10 DPS (clickable job_id → `/result/{id}`)

---

### 📈 Traffic
Site traffic analytics. Auto-refreshes every **60 seconds**.

- Visits today / 7 days / 30 days, unique users (based on IP hash)
- Daily chart — total vs unique visitors (30 days)
- Hourly traffic heatmap (last 7 days)
- Top 10 most visited pages (30 days)

---

### 📰 News
Manage news items displayed on the homepage.

- **Add** — title + content (plain text or Markdown) + publish checkbox
- **Edit** — click an entry, modify it, save
- **Delete** — `×` button next to an entry
- **Publish** — "published" toggle — unpublished news is not visible to users

---

### 👥 Users
List of active users with basic statistics.

| Column | Description |
|--------|-------------|
| Character | Name + class + spec from the last simulation |
| Simulations | Total count |
| Avg DPS | Average DPS across all simulations |
| Last activity | Date of last simulation |

Clicking a user opens a modal with their last 20 simulations.

> ⚠️ The list currently shows only users who have run at least one simulation. This is a known issue — tracked in [#47](https://github.com/MiyazakiTakara/simcraft-web/issues/47).

---

### 📋 Logs
Real-time application logs. Auto-refreshes every **15 seconds**.

- Filter by level: `INFO`, `WARNING`, `ERROR`
- Level colors: INFO — grey, WARNING — yellow, ERROR — red
- Frontend logs (JS errors) are reported via the `/admin/api/client-error` endpoint

---

### ⚙️ Limits
System limit configuration.

| Setting | Default | Description |
|---------|---------|-------------|
| Max concurrent simulations | 3 | How many simc processes can run simultaneously |
| Rate limit / min | 5 | Max simulations per minute per user |
| Simulation timeout | 360s | After how many seconds simc will be killed |

> ⚠️ Limit changes are temporary — they are not persisted to a file. To make them permanent, update the environment variables in `.env` and restart the container.

---

### 🏥 Health
Status of all services. Auto-refreshes every **60 seconds**.

| Service | What it checks |
|---------|----------------|
| Database | `SELECT 1` on PostgreSQL |
| Blizzard API | Fetching OAuth token |
| Keycloak | `/.well-known/openid-configuration` |
| simc binary | File existence and execute permissions |
| Results dir | Directory existence and writability |
| simc version | Compares local version with latest on GitHub (1h cache) |

---

### 🔧 Tasks
Currently running simulations. Auto-refreshes every **10 seconds**.

- List of job_id + start time
- **Cancel** button — immediately terminates the task (status: `error`, reason: `Cancelled by admin`)

---

### 🎨 Appearance
UI customization without redeployment.

- **Header title** — text next to the emoji in the navigation bar
- **Hero title** — title on the homepage (e.g. `World of Warcraft`)
- **Custom hero text** — if filled in, replaces the entire default hero block
- **Emoji** — choose from the palette or type manually

Changes are saved to `config/appearance.json` and take effect immediately.

---

### 📚 Documentation
Markdown file browser from the `docs/` directory.

- Click a file in the left sidebar — content is rendered from Markdown to HTML
- Syntax highlighting for code blocks (`github-dark` theme)
- **Copy Markdown** button — copies the raw `.md` to clipboard
- Files are cached in memory during the session — refresh the page if you edited a file
- Documentation language follows the interface language setting

---

## Security

- Admin session expires after **8 hours**
- Access requires a Keycloak account with the `admin` role
- The panel should eventually be moved to a subdomain with an IP allowlist (see issue [#45](https://github.com/MiyazakiTakara/simcraft-web/issues/45))
- JS error logs are rate-limited — max 10 req/min per IP (endpoint `/admin/api/client-error`)
