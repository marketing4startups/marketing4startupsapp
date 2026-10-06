# Marketing4Startups

A local-first marketing planning app with secure accounts, startup profiles, interview notes, and growth experiments.

## Supabase database (new integration)

`supabase/migrations/` defines the Supabase Auth-backed user, workspace, startup profile, experiment, and interview tables. Passwords and login sessions belong to Supabase Auth; the app tables do not store credentials. Row-level security is enabled and forced on every app table, anonymous access is revoked, and authenticated users receive only the table and column permissions their app workflows need. Workspace membership and record ownership are checked in database policies.

To use this schema with a Supabase project:

1. Install Docker Desktop and the Supabase CLI, then sign in with `supabase login`.
2. From this folder, run `supabase link --project-ref <your-project-ref>` and `supabase db push`.
3. In the Supabase Dashboard, configure Auth sign-up and email verification for your project. Keep the service-role key server-side; the browser must use only the publishable/anon key.
4. Have the authenticated client call the `initialize_account` RPC once after sign-up to create the user's profile, workspace, owner membership, and startup profile atomically.

The app currently continues to use its existing local Python authentication/database path. The migration is the secure Supabase database foundation; switching the sign-in UI and API to Supabase Auth is a separate integration step. Do not collect production accounts until that client/API integration is complete and tested against your project.

`supabase/tests/user_data_rls_test.sql` checks RLS flags and API grants. Run it with `supabase test db` after starting the local Supabase stack (`supabase start`); Docker is required. This environment did not have Docker available, so the migration and pgTAP suite could not be executed here.

## Run with Docker and PostgreSQL

This is the recommended setup when you want account data in a SQL server.

1. Install and start Docker Desktop.
2. Run `start-docker.bat`. The first run creates a private `.env` file from `.env.example` and stops so you can set separate random passwords for PostgreSQL and pgAdmin.
3. Run `start-docker.bat` again. Docker builds the app, starts PostgreSQL, waits for its health check, then starts the app.
4. Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

### Docker Engine build-cache settings

`docker-engine-settings.json` contains the requested Docker Engine settings: BuildKit cache garbage collection enabled with a 20 GB retention limit, and experimental features disabled. These are Docker Desktop/Engine-wide settings, not Compose settings. In Docker Desktop, open **Settings → Docker Engine**, merge these keys into the existing JSON, then select **Apply & Restart**. Preserve any other existing engine settings.

You can also copy `.env.example` to `.env`, set all three passwords/emails, and run `docker compose up --build` in this folder. The app and pgAdmin connect to PostgreSQL over Docker's private network. PostgreSQL's port is published on `127.0.0.1:5432` for local tools, the web app on `127.0.0.1:8000`, and pgAdmin on `127.0.0.1:5050`. Docker volumes keep the database, pgAdmin settings, and private app key across restarts. To stop the containers, press Ctrl+C; to start them again use `docker compose up`.

### Manage the database on this PC

Open [http://127.0.0.1:5050](http://127.0.0.1:5050) after the containers start. Sign in with `PGADMIN_DEFAULT_EMAIL` and `PGADMIN_DEFAULT_PASSWORD` from `.env`. In pgAdmin, register a server with these connection details:

- **Host:** `db`
- **Port:** `5432`
- **Maintenance database:** `marketing4startups`
- **Username:** `m4s_app`
- **Password:** `POSTGRES_PASSWORD` from `.env`

The hostname `db` works from pgAdmin inside Docker. For a desktop PostgreSQL client installed directly on Windows, connect to `127.0.0.1:5432` with the same database username and password. Both admin interfaces are bound to loopback and aren't published to your LAN.

### Connecting from a separate Codex Docker sandbox

Use this PostgreSQL connection URL inside the sandbox, replacing the password with the value in `.env`:

```text
postgresql://m4s_app:<POSTGRES_PASSWORD>@host.docker.internal:5432/marketing4startups
```

The default `POSTGRES_BIND_ADDRESS=127.0.0.1` is safest for host-local use. If the separate sandbox cannot reach the host's loopback-bound port, set `POSTGRES_BIND_ADDRESS=0.0.0.0` in `.env`, recreate the database with `docker compose up -d --force-recreate db`, and allow port 5432 only from the sandbox in your host firewall. Use a strong unique password; do not expose this database to the public internet.

To make a database backup, run `docker compose exec -T db pg_dump -U m4s_app marketing4startups > marketing4startups-backup.sql`. Keep that backup private and store it separately from the Docker host.

## Run without Docker

For a quick local preview, double-click `start.bat`, or run `python server.py` in this folder. It uses SQLite in `data/marketing4startups.sqlite3`. This mode does not need third-party Python packages. Do not open `index.html` directly with `file://` for account use; sign-in requires the local server.

## Database and sign-in

When `DATABASE_URL` is set, the app uses PostgreSQL (`schema.postgres.sql`) and the `psycopg` driver. Otherwise, it uses the SQLite schema (`schema.sql`). Both backends store user accounts, workspaces, memberships, startup profiles, interviews, experiments, sessions, and sign-in throttling records.

Passwords are stored as PBKDF2-SHA256 hashes. Login uses generic errors and throttling. Sessions use random tokens stored as hashes, HttpOnly and SameSite=Strict cookies, Origin checks on writes, and a Secure cookie when a trusted HTTPS proxy sets `X-Forwarded-Proto: https`. The local Docker setup serves HTTP on loopback; do not expose it publicly without TLS and production hardening.

## Privacy and deployment

The app includes data export, individual record removal, and password-confirmed account deletion. Read `privacy-notice.md` and complete `gdpr-process.md` before collecting real user data. This prototype does not provide email verification or recovery, account support, a hosted backup/restore policy, production monitoring, or a privacy-request inbox. Local Docker is for development and private use, not a production service or GDPR certification.

