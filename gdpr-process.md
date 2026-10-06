# GDPR operating process · Marketing4Startups

**Status:** product implementation and operator checklist, not a legal certification. Confirm the controller, lawful bases, processor roles, supplier terms, and jurisdiction-specific requirements before launch. Do not describe this prototype as GDPR-compliant until the outstanding launch controls below are completed.

## 1. Current-system audit

### What exists now

- A Python standard-library HTTP server serves the marketing homepage and API.
- SQLite stores user accounts, workspace membership, startup profiles, experiments, interview notes, sessions, and short-lived sign-in throttles.
- The app uses account email and password; it does not collect payment details, analytics, advertising identifiers, newsletter preferences, or health/biometric data.
- User-entered free text can contain other people's personal data. Interview notes therefore require a warning and minimisation practice.
- The account data export, profile correction, individual experiment/note removal, and re-authenticated account deletion are implemented in Settings.
- Google Fonts network requests were removed. No analytics or advertising integration is configured.
- The app is local-only by default. Hosting, backups, support access, email delivery, and production identity/contact are not configured.

### Data-flow and records-of-processing draft

| Activity | People / data | Purpose | Proposed basis to confirm | Recipients / retention |
|---|---|---|---|---|
| Account operation | Founder account: email, password hash, account date | Create and operate requested workspace | Contract / pre-contract steps | Local SQLite; until account deletion or approved inactive-account limit |
| Workspace planning | Founder-entered startup profile, economic figures, experiment content | Save and display the user's growth plan | Contract | Local SQLite; until account deletion |
| Customer interview notes | Potentially identifiable interview subjects; note and commitment entered by the startup user | Let startup user organise discovery work | Startup's basis; platform role depends on hosting and instructions | Local SQLite; user can remove note/account; hosted mode needs Article 28 analysis and terms |
| Sign-in protection | HMAC of network address/email using an installation key stored in the private data directory; attempts and timestamps | Throttle credential guessing and signup abuse | Legitimate interests, subject to a written LIA | SQLite; 15-minute login window / one-hour signup window; stale rows cleaned on requests |
| Session management | Hashed random token and expiry | Maintain sign-in state | Necessary for requested service | SQLite; 30-day expiry and cleanup on app requests |
| Essential browser state | HttpOnly session cookie; non-identifying theme preference | Authentication and interface preference | Necessary cookie / storage analysis under applicable ePrivacy rules | Browser; session token expires after 30 days; theme preference remains until cleared |

This table is a draft Article 30 record. The actual controller must add legal name/contact, processor/DPO details where applicable, real hosting/recipient countries, retention exceptions, safeguards, and a record owner/date. Assess whether Article 30(5)'s small-organisation exception applies; do not assume it removes the need for records when processing is not occasional or may pose risk.

## 2. Responsibilities before collecting real data

1. **Name the controller.** Add the responsible legal person/entity, privacy contact, establishment, and supervisory authority. Decide the service's role separately for account data and user-entered interview data.
2. **Confirm each lawful basis.** Contract is proposed for the account/workspace. Legitimate interests is proposed for sign-in abuse prevention and needs a documented purpose/necessity/balancing assessment and an objection route. Do not use bundled consent for core product features.
3. **Map vendors and transfers.** Record the host, backups, email provider, monitoring, support, and any subprocessors. Add Article 28 terms where acting as processor. Check transfer safeguards before any non-EEA transfer. Update the notice and record before enabling vendors.
4. **Set retention.** Choose an inactive-account expiry and backup deletion schedule. Keep only records needed for a documented period. Decide if narrow legal claims/tax records must be retained after account closure, isolate them, limit access, document basis and deletion date.
5. **Review security and privacy by design.** Threat-model shared hosting, administrators, database backups, recovery, session revocation, and account takeover. Add secure production hosting/TLS, least privilege, tested encrypted backups, monitoring/alerting, dependency and vulnerability maintenance, and an incident contact. The current built-in server and local plaintext SQLite file are development-only.
6. **Screen for a DPIA.** Record a screening decision for each materially new use. Carry out a DPIA before processing likely to create high risk; consult the DPC before starting if high residual risk remains where required.
7. **Review children/sensitive data.** The product is not designed for children or special-category data. Add product controls and an escalation path if a launch audience or new feature changes this.

## 3. Privacy notice and collection process

- Present the notice before account creation and link it from the landing page and account settings.
- Use plain language to name purposes, data categories, legal bases, recipients, transfers, retention, rights, complaint route, and whether fields are necessary.
- Warn users not to store interviewee names, special-category data, or unnecessary personal details in notes. If a startup uses the app as processor, provide customer instructions and a DPA before accepting those records.
- Do not add analytics or non-essential tracking without a separate necessity and consent/ePrivacy review. There is no consent banner while no such technology is used.
- Keep a dated notice version and a record of material changes shown to users.

## 4. Data-subject request workflow

The controller, not an automated form alone, owns each request.

1. **Receive and log** the date, request type, channels, scope, owner, due date, and secure case reference. Avoid copying extra identity documents.
2. **Verify proportionately** using the signed-in account or other reasonable checks if identity is in doubt. Do not disclose one person's data to another workspace member without authority.
3. **Scope and search** account, workspace, SQLite records, backups, host logs, support systems, and processors using the record of processing. Check third-party rights and statutory exceptions.
4. **Respond without undue delay and normally within one month.** For a complex or numerous request, extend by up to two further months only when permitted; tell the requester within the first month and explain why. Requests are normally free; charge or refusal only when legally justified and explain the complaint route.
5. **Action rights:**
   - Access: provide a copy plus purposes, categories, recipients, retention, source, rights, safeguards, and relevant automated-decision information.
   - Rectification: correct profile/records and communicate corrections to recipients when required. Current UI edits onboarding fields and allows removal/re-entry of saved interview/experiment items.
   - Erasure: evaluate applicable grounds and exceptions. The app's delete-account action reauthenticates and cascades workspace data, then clears the active session. Check backups and any legal hold separately.
   - Restriction/object: stop or limit the relevant processing while eligibility is assessed; preserve only allowed storage and notify recipients where required.
   - Portability: provide a commonly used machine-readable format where Article 20 conditions apply. The account JSON export is available to signed-in users.
   - Withdraw consent: no consent-based marketing processing currently exists. If optional consent is added later, record it separately and make withdrawal as easy as giving it.
6. **Close the case** with response date, actions, any exception/reason, recipients notified, and secure deletion of request working copies under the case-retention policy.

The GDPR's normal response period and limited extension rules are in Article 12. Rights have conditions/exceptions, so the controller should assess rather than promise unconditional deletion or portability.

## 5. Retention and deletion runbook

- Account owner: use **Settings → Privacy & your data → Download my data** before deletion if a portable copy is wanted.
- Account owner: use **Delete my account**, re-enter the password, and type `DELETE`. The server deletes the account, workspace, profile, interviews, experiments, and sessions through database cascades; secure-delete is enabled and a WAL truncate checkpoint is requested.
- Saved interview/experiment: use **Remove** in Privacy & your data. Correct startup profile via **Edit onboarding**; to correct other saved notes, remove and re-enter the corrected record.
- Operator: verify the deployed backup, OS snapshot, support, and log retention separately. SQLite deletion cannot remove copies made by the device owner or hosting/backups outside this app.
- Operator: run and retain a periodic review of old accounts and data; choose an inactive-account schedule before hosting. The current app has no scheduled inactive-user deletion.

## 6. Personal-data breach runbook

1. Report suspected exposure/loss immediately to the named privacy/security contact; preserve relevant evidence and timestamps.
2. Contain access (disable affected credentials/sessions, isolate host, stop an unsafe export), protect logs, assess affected people/data/scale and likely consequences, and record the decision.
3. If acting as processor, alert the controller without undue delay under the service contract. If controller, notify the competent DPA without undue delay and, where feasible, within 72 hours of awareness unless the breach is unlikely to risk people's rights and freedoms. Give reasons if late.
4. Communicate with affected people without undue delay where a breach is likely to create high risk, unless a GDPR exception applies. Include practical protective steps.
5. Document every breach, including incidents not reported to the DPA: facts, effects, risk decision, notifications, mitigation, and follow-up. Review root cause and test corrective measures.

## 7. Incident-free launch checklist

- [ ] Add controller legal identity and monitored privacy/security contact to landing, notice, and support procedure.
- [ ] Approve the ROPA, legal-basis assessment/LIA, processor-role analysis, data retention schedule, and DPIA screening.
- [ ] Decide if a DPO/representative is legally required and add them where applicable.
- [ ] Choose hosting and data regions; execute DPAs, review subprocessors/transfers, document backup/log deletion.
- [ ] Add email verification and secure account recovery before hosted accounts are used.
- [ ] Deploy behind maintained HTTPS infrastructure; configure trusted proxy headers; restrict filesystem/database access; test restore and account deletion from backups.
- [ ] Review access controls, session revocation, rate limiting, monitoring, security updates, and incident contacts.
- [ ] Confirm DSAR channel, one-month case tracking, identity checks, exceptions, and processor-to-controller escalation.
- [ ] Review fields and warnings to prevent unnecessary/sensitive interviewee data; explain customer-controller duties.
- [ ] Review every new vendor, cookie, analytics tool, purpose, and data field before release; update the notice and ROPA first.

## 8. Official references

- [GDPR consolidated text, EUR-Lex](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:02016R0679-20160504) — in particular Articles 5, 6, 12–22, 25, 28, 30, 32–35.
- [Irish Data Protection Commission: rights of individuals](https://www.dataprotection.ie/sites/default/files/uploads/2018-12/Rights-of-Individuals-under-the-General-Data-Protection-Regulation-04-2018.pdf).
- [EDPB: privacy by design and by default](https://www.edpb.europa.eu/topics/ai-and-technology/privacy-by-design-and-by-default_en).
- [EDPB: personal data breaches](https://www.edpb.europa.eu/topics/security-data-breaches/personal-data-breaches_en).
- [Irish Data Protection Commission: breach notifications](https://www.dataprotection.ie/en/organisations/know-your-obligations/quick-guide-gdpr-breach-notifications).
