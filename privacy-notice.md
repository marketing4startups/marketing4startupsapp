# Privacy notice · Marketing4Startups prototype

**Draft for product review.** This notice describes the local prototype as it is currently built. It is not a confirmation that a future hosted service complies with the GDPR. Before public release, the service operator must add its legal identity, a working privacy contact, verified lawful bases, actual hosting/recipient details, and a reviewed retention schedule.

## Who is responsible?

The operator's full legal name and contact details are not configured yet. In this local prototype, the person or organisation that runs the server controls the SQLite file on that device. A hosted service must identify its controller and contact point here. If the service stores a startup's interview notes about that startup's customers, the startup may be controller for those notes and the service may act as processor; confirm the roles for the real deployment and put the required processor terms in place.

**Controller:** [Add legal name]

**Privacy contact:** [Add monitored email or postal address]

## What information is processed?

- Account: email address, password hash, account creation time, and sign-in session token hash/expiry.
- Workspace: startup name and owner membership.
- Startup setup: stage, target customer, customer pain, current alternatives, differentiators, value, category, channel choices, and business/economic figures entered during setup.
- Growth work: experiment idea, channel, hypothesis, status, spending limit, review date, and creation time.
- Interview notes: recent customer event and selected commitment, when the user saves a note.
- Abuse prevention: short-lived HMAC-keyed identifiers derived from the network address and email for signup/sign-in throttling; the installation key is kept in the local private data directory. The source address and raw password are not saved in the user tables.
- Browser storage: an essential, HttpOnly sign-in cookie and a non-identifying display-theme preference. Startup profile answers are fetched from SQLite and held in memory while the app is open; the app clears any legacy local onboarding copy.

Do not put special-category information, passwords, payment-card details, or unnecessary names/contact details of interviewees into free-text fields. The app does not need them.

## Why and on what basis?

The working design uses account/workspace data to provide the account and saved tools (proposed Article 6(1)(b) basis: steps requested by the user / contract), and short-lived login-abuse controls to protect the service (proposed Article 6(1)(f) basis: legitimate interests). The operator must confirm the applicable basis and, for legitimate interests, document the purpose, necessity, and balancing assessment before release. Do not label required account processing as consent. There is currently no analytics, advertising, newsletter, or marketing-consent feature.

For interview information about a startup's own customers, the startup must decide its lawful basis, provide any required notice, and instruct the service appropriately. A hosted version must determine whether it is a processor for that content, offer Article 28 terms, and list its sub-processors and transfer locations.

## Where data goes

In the default local mode, the app writes to `data/marketing4startups.sqlite3` on the computer running `server.py`. In Docker mode, account data is stored in the PostgreSQL Docker volume named `postgres_data`, and the app's authentication key is stored in `app_private_data`. The Docker database is not published on a host port; the app is bound to `127.0.0.1:8000`. The Docker host administrator can access container volumes and backups. A hosted installation will have different recipients and must update this notice before collection.

## Retention

- Account and workspace content: until the owner deletes the account, or until a verified retention schedule for inactive accounts is adopted. There is no inactive-account expiry yet.
- Sessions: expire after 30 days and expired rows are purged on app requests/sign-ins and by a one-minute background cleanup while the server runs.
- Sign-in attempt identifiers: rolling rate-limit windows of 15 minutes (sign-in) and up to one hour (signup); stale rows are cleaned during app requests and by a one-minute background cleanup while the server runs. The identifiers are HMAC-keyed for the lifetime of the running server process.
- App profile in the browser: not persisted after the SQL integration; only loaded into memory while signed in. Display theme is stored separately and is not linked to account identity.
- Security logs: server request lines are printed to the local terminal and are not written to a configured file by this prototype. The computer/hosting provider may have its own system logs.
- Backups: the prototype does not make or control backups. Any operator-created backup needs its own access, retention, and deletion rules.

The operator must set an inactive-account and backup-deletion schedule before operating a hosted service.

## Rights and choices

Depending on context and applicable exceptions, people may ask for access, correction, erasure, restriction, portability, or object to processing based on legitimate interests. The Settings → Privacy & your data area provides a JSON download, correction of startup setup, removal of saved experiments/interview notes, and account deletion after password confirmation. To exercise another right or ask a question, use the privacy contact above (to be configured). The controller normally responds within one month; a permitted extension requires notice within that first month. A person can also complain to the competent supervisory authority. In Ireland that is the Data Protection Commission.

Erasure is subject to statutory exceptions and other legal obligations. This prototype does not provide email verification, account recovery, or a process for retaining narrowly required legal records after an account is removed; the controller must decide and document those cases before public service use.

## Security

Passwords use PBKDF2-SHA256; session identifiers are random and only their hashes are stored. Sessions use HttpOnly and SameSite=Strict cookies; the Secure flag is added behind HTTPS when a trusted proxy sets `X-Forwarded-Proto: https`. Writes compare browser origins, sign-in is throttled, database access is scoped to the signed-in workspace, and account removal rechecks the password. This small local prototype is not a substitute for a production security review, TLS termination, operational monitoring, tested recovery/backups, vulnerability handling, or access controls on the host.

## Changes to this notice

Update this notice when purposes, data categories, recipients, transfer locations, retention, or rights controls change. Keep dated versions and record when a material change is shown to signed-in users.

