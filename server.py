#!/usr/bin/env python3
"""Local SQL-backed server for the Marketing4Startups prototype."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "marketing4startups.sqlite3"
SCHEMA_PATH = ROOT / "schema.sql"
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if DATABASE_URL:
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeError("PostgreSQL mode needs psycopg. Run pip install -r requirements.txt.") from exc
    DB_ERROR = psycopg.Error
    DB_INTEGRITY_ERROR = psycopg.IntegrityError
else:
    DB_ERROR = sqlite3.Error
    DB_INTEGRITY_ERROR = sqlite3.IntegrityError
COOKIE_NAME = "m4s_session"
SESSION_DAYS = 30
PASSWORD_ITERATIONS = 310_000
MAX_BODY = 64 * 1024
AUTH_SCOPE_KEY_PATH = DATA_DIR / ".auth_scope_key"
DUMMY_SALT = bytes.fromhex("fb6e77c463514a79598c871729b404c2")
DUMMY_HASH = "pbkdf2_sha256$310000$fb6e77c463514a79598c871729b404c2$" + hashlib.pbkdf2_hmac(
    "sha256", b"not-a-user-password", DUMMY_SALT, PASSWORD_ITERATIONS
).hex()


def connect():
    if DATABASE_URL:
        return PostgresConnection(psycopg.connect(DATABASE_URL, row_factory=dict_row))
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA journal_mode = WAL")
    db.execute("PRAGMA secure_delete = ON")
    return db


class PostgresCursor:
    def __init__(self, cursor):
        self.cursor = cursor
        self.lastrowid = None

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    @property
    def rowcount(self):
        return self.cursor.rowcount


class PostgresConnection:
    """Small compatibility layer so the same request handlers can use PostgreSQL."""
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self.connection.commit()
            else:
                self.connection.rollback()
        finally:
            self.connection.close()

    def execute(self, sql, params=()):
        sql = sql.replace("strftime('%Y-%m-%dT%H:%M:%fZ','now')",
                          "to_char(clock_timestamp() at time zone 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS.MS\"Z\"')")
        sql = sql.replace("?", "%s")
        generated_id_table = None
        if sql.lstrip().upper().startswith("INSERT INTO ") and " RETURNING " not in sql.upper():
            generated_id_table = sql.lstrip()[len("INSERT INTO "):].split("(", 1)[0].strip().lower()
            if generated_id_table in {"users", "workspaces", "experiments", "customer_interviews", "sessions", "auth_attempts"}:
                sql = sql.rstrip().rstrip(";") + " RETURNING id"
        cursor = self.connection.execute(sql, params)
        wrapped = PostgresCursor(cursor)
        if generated_id_table:
            row = cursor.fetchone()
            wrapped.lastrowid = row["id"] if row else None
        return wrapped

    def commit(self):
        self.connection.commit()


def initialize():
    global AUTH_SCOPE_KEY
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        AUTH_SCOPE_KEY = AUTH_SCOPE_KEY_PATH.read_bytes()
        if len(AUTH_SCOPE_KEY) != 32:
            raise RuntimeError("The local authentication scope key is invalid.")
    except FileNotFoundError:
        key = secrets.token_bytes(32)
        try:
            with AUTH_SCOPE_KEY_PATH.open("xb") as key_file:
                key_file.write(key)
            if os.name != "nt":
                os.chmod(AUTH_SCOPE_KEY_PATH, 0o600)
            AUTH_SCOPE_KEY = key
        except FileExistsError:
            AUTH_SCOPE_KEY = AUTH_SCOPE_KEY_PATH.read_bytes()
    with connect() as db:
        if DATABASE_URL:
            schema = (ROOT / "schema.postgres.sql").read_text(encoding="utf-8")
            for statement in schema.split(";"):
                if statement.strip():
                    db.execute(statement)
        else:
            db.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AppHandler(SimpleHTTPRequestHandler):
    server_version = "Marketing4Startups/1.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if self.headers.get("X-Forwarded-Proto") == "https":
            self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        super().end_headers()

    def send_json(self, status, payload, headers=None):
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        if headers:
            for key, value in headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(raw)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_BODY:
            raise ValueError("Request is too large.")
        payload = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(payload, dict):
            raise ValueError("Request must be a JSON object.")
        return payload

    def request_cookie(self):
        cookie = SimpleCookie()
        cookie.load(self.headers.get("Cookie", ""))
        morsel = cookie.get(COOKIE_NAME)
        return morsel.value if morsel else None

    def check_origin(self):
        origin = self.headers.get("Origin")
        if not origin:
            return True
        parsed = urlparse(origin)
        forwarded = self.headers.get("X-Forwarded-Proto", "http").split(",", 1)[0].strip()
        if parsed.scheme in ("http", "https") and parsed.netloc.lower() == self.headers.get("Host", "").lower() and parsed.scheme == forwarded:
            return True
        self.send_json(HTTPStatus.FORBIDDEN, {"error": "This request could not be verified. Reload the page and try again."})
        return False

    @staticmethod
    def auth_scope(value):
        return hmac.new(AUTH_SCOPE_KEY, value.encode("utf-8"), hashlib.sha256).hexdigest()

    @staticmethod
    def rate_limited(db, scope_hash, limit, seconds):
        cutoff = (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()
        db.execute("DELETE FROM auth_attempts WHERE scope_hash=? AND attempted_at < ?", (scope_hash, cutoff))
        count = db.execute("SELECT COUNT(*) AS total FROM auth_attempts WHERE scope_hash=? AND attempted_at>=?",
                           (scope_hash, cutoff)).fetchone()
        count = count["total"] if DATABASE_URL else count[0]
        return count >= limit

    @staticmethod
    def record_auth_attempt(db, scope_hash):
        db.execute("INSERT INTO auth_attempts(scope_hash) VALUES(?)", (scope_hash,))

    def current_user(self, db):
        token = self.request_cookie()
        if not token:
            return None
        return db.execute(
            "SELECT u.id,u.email,w.id AS workspace_id,w.name AS workspace_name "
            "FROM sessions s JOIN users u ON u.id=s.user_id "
            "JOIN workspace_members m ON m.user_id=u.id "
            "JOIN workspaces w ON w.id=m.workspace_id "
            "WHERE s.token_hash=? AND s.expires_at > ? ORDER BY w.id LIMIT 1",
            (token_digest(token), datetime.now(timezone.utc).isoformat()),
        ).fetchone()

    def create_session(self, db, user_id):
        token = secrets.token_urlsafe(32)
        expires = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
        db.execute("DELETE FROM sessions WHERE expires_at <= ?", (datetime.now(timezone.utc).isoformat(),))
        db.execute("INSERT INTO sessions(user_id,token_hash,expires_at) VALUES(?,?,?)",
                   (user_id, token_digest(token), expires.isoformat()))
        secure = "; Secure" if self.headers.get("X-Forwarded-Proto") == "https" else ""
        return f"{COOKIE_NAME}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={SESSION_DAYS * 86400}{secure}"

    def do_GET(self):
        path = urlparse(self.path).path
        if path.startswith("/api/"):
            return self.api_get(path)
        if path == "/data" or path.startswith("/data/") or path.endswith((".sqlite3", ".sqlite3-wal", ".sqlite3-shm")):
            return self.send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
        resolved = Path(super().translate_path(self.path)).resolve()
        try:
            resolved.relative_to(DATA_DIR.resolve())
            return self.send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
        except ValueError:
            pass
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        if not path.startswith("/api/"):
            return self.send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
        if not self.check_origin():
            return
        try:
            data = self.read_json()
        except (ValueError, json.JSONDecodeError):
            return self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Please send valid form data."})
        if path == "/api/signup":
            return self.signup(data)
        if path == "/api/login":
            return self.login(data)
        if path == "/api/logout":
            return self.logout()
        if path == "/api/experiments":
            return self.add_experiment(data)
        if path == "/api/interviews":
            return self.add_interview(data)
        return self.send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})

    def do_DELETE(self):
        path = urlparse(self.path).path
        if not self.check_origin():
            return
        if path != "/api/account":
            match = re.fullmatch(r"/api/(experiments|interviews)/(\d+)", path)
            if not match:
                return self.send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            table = "experiments" if match.group(1) == "experiments" else "customer_interviews"
            record_id = int(match.group(2))
            with connect() as db:
                user = self.current_user(db)
                if not user:
                    return self.send_json(HTTPStatus.UNAUTHORIZED, {"error": "Please sign in."})
                result = db.execute(f"DELETE FROM {table} WHERE id=? AND workspace_id=?",
                                    (record_id, user["workspace_id"]))
                if result.rowcount == 0:
                    return self.send_json(HTTPStatus.NOT_FOUND, {"error": "That record could not be found."})
            return self.send_json(HTTPStatus.OK, {"ok": True})
        try:
            data = self.read_json()
        except (ValueError, json.JSONDecodeError):
            return self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Please send valid confirmation details."})
        return self.delete_account(data)

    def do_PUT(self):
        path = urlparse(self.path).path
        if path != "/api/profile":
            return self.send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
        if not self.check_origin():
            return
        try:
            data = self.read_json()
        except (ValueError, json.JSONDecodeError):
            return self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Please send valid form data."})
        return self.save_profile(data)

    def api_get(self, path):
        with connect() as db:
            now = datetime.now(timezone.utc).isoformat()
            auth_cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
            db.execute("DELETE FROM sessions WHERE expires_at<=?", (now,))
            db.execute("DELETE FROM auth_attempts WHERE attempted_at<?", (auth_cutoff,))
            user = self.current_user(db)
            if path == "/api/me":
                if not user:
                    return self.send_json(HTTPStatus.UNAUTHORIZED, {"error": "Please sign in."})
                return self.send_json(HTTPStatus.OK, {"id": user["id"], "email": user["email"],
                                                       "workspace": user["workspace_name"]})
            if not user:
                return self.send_json(HTTPStatus.UNAUTHORIZED, {"error": "Please sign in."})
            if path == "/api/profile":
                row = db.execute("SELECT * FROM startup_profiles WHERE user_id=?", (user["id"],)).fetchone()
                profile = self.profile_to_json(row)
                if profile:
                    profile["company"] = user["workspace_name"]
                return self.send_json(HTTPStatus.OK, {"profile": profile})
            if path == "/api/experiments":
                rows = db.execute("SELECT id,name,channel,status,hypothesis,cost_limit,review_date,created_at "
                                  "FROM experiments WHERE workspace_id=? ORDER BY id DESC",
                                  (user["workspace_id"],)).fetchall()
                return self.send_json(HTTPStatus.OK, {"experiments": [dict(row) for row in rows]})
            if path == "/api/interviews":
                rows = db.execute("SELECT id,recent_event,commitment,created_at FROM customer_interviews "
                                  "WHERE workspace_id=? ORDER BY id DESC", (user["workspace_id"],)).fetchall()
                return self.send_json(HTTPStatus.OK, {"interviews": [dict(row) for row in rows]})
            if path == "/api/privacy/export":
                profile_row = db.execute("SELECT * FROM startup_profiles WHERE user_id=?", (user["id"],)).fetchone()
                profile = self.profile_to_json(profile_row) or {}
                profile["company"] = user["workspace_name"]
                interviews = db.execute("SELECT id,recent_event,commitment,created_at FROM customer_interviews "
                                        "WHERE workspace_id=? ORDER BY id", (user["workspace_id"],)).fetchall()
                experiments = db.execute("SELECT id,name,channel,status,hypothesis,cost_limit,review_date,created_at "
                                         "FROM experiments WHERE workspace_id=? ORDER BY id",
                                         (user["workspace_id"],)).fetchall()
                account = db.execute("SELECT created_at FROM users WHERE id=?", (user["id"],)).fetchone()
                login_scope = self.auth_scope("login-email:" + user["email"].lower())
                sign_in_attempts = db.execute("SELECT attempted_at FROM auth_attempts WHERE scope_hash=? ORDER BY attempted_at",
                                              (login_scope,)).fetchall()
                sessions = db.execute("SELECT created_at,expires_at FROM sessions WHERE user_id=? ORDER BY created_at",
                                      (user["id"],)).fetchall()
                return self.send_json(HTTPStatus.OK, {
                    "export_format": "Marketing4Startups personal data export",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "account": {"email": user["email"], "created_at": account["created_at"]},
                    "sign_in_attempt_timestamps": [row["attempted_at"] for row in sign_in_attempts],
                    "session_dates": [dict(row) for row in sessions],
                    "workspace": {"name": user["workspace_name"], "role": "owner"},
                    "startup_profile": profile,
                    "customer_interviews": [dict(row) for row in interviews],
                    "growth_experiments": [dict(row) for row in experiments],
                    "privacy_information": {
                        "purposes": ["provide the account and workspace", "save startup setup and user-created marketing records", "protect sign-in against abuse"],
                        "recipients": ["this local application and its PostgreSQL database in Docker" if DATABASE_URL else "this local application and its SQLite database", "no analytics or advertising recipient is configured"],
                        "automated_decisions": "None",
                        "retention": "Account content remains until deleted by the user; expired sessions and short-lived sign-in counters are cleaned up during app requests."
                    }
                }, {"Content-Disposition": 'attachment; filename="marketing4startups-data-export.json"'})
        return self.send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})

    @staticmethod
    def profile_to_json(row):
        if not row:
            return None
        return {"company": "", "stage": row["startup_stage"],
                "icp": row["best_fit_customer"], "pain": row["customer_pain"],
                "alt": row["current_alternative"], "diff": row["differentiator"],
                "value": row["customer_value"], "category": row["market_category"],
                "arpa": row["monthly_revenue_per_customer"], "margin": row["gross_margin_percent"],
                "cac": row["cac_limit"], "churn": row["monthly_churn_percent"],
                "payback": row["payback_months"], "ratio": row["ltv_cac_target"],
                "channels": json.loads(row["channel_candidates"]), "completedAt": row["completed_at"]}

    def signup(self, data):
        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", ""))
        workspace = str(data.get("workspace", "")).strip()[:100]
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 254:
            return self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Enter a valid email address."})
        if len(password) < 12 or len(password) > 256:
            return self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Use a password with at least 12 characters."})
        ip_scope = self.auth_scope("signup-ip:" + (self.client_address[0] if self.client_address else "unknown"))
        try:
            with connect() as db:
                if self.rate_limited(db, ip_scope, 6, 3600):
                    return self.send_json(HTTPStatus.TOO_MANY_REQUESTS,
                                          {"error": "Too many account attempts. Please wait before trying again."})
                self.record_auth_attempt(db, ip_scope)
                db.commit()
                cur = db.execute("INSERT INTO users(email,password_hash) VALUES(?,?)", (email, hash_password(password)))
                user_id = cur.lastrowid
                workspace_name = workspace or "My startup"
                cur = db.execute("INSERT INTO workspaces(name,created_by) VALUES(?,?)", (workspace_name, user_id))
                workspace_id = cur.lastrowid
                db.execute("INSERT INTO workspace_members(workspace_id,user_id,role) VALUES(?,?,'owner')", (workspace_id, user_id))
                db.execute("INSERT INTO startup_profiles(user_id,workspace_id) VALUES(?,?)", (user_id, workspace_id))
                cookie = self.create_session(db, user_id)
        except DB_INTEGRITY_ERROR:
            return self.send_json(HTTPStatus.CONFLICT, {"error": "We could not create an account with those details. Try signing in or use another email."})
        return self.send_json(HTTPStatus.CREATED, {"id": user_id, "email": email, "workspace": workspace_name},
                              {"Set-Cookie": cookie})

    def login(self, data):
        email = str(data.get("email", "")).strip().lower()
        password = str(data.get("password", ""))
        ip_scope = self.auth_scope("login-ip:" + (self.client_address[0] if self.client_address else "unknown"))
        email_scope = self.auth_scope("login-email:" + email)
        with connect() as db:
            if self.rate_limited(db, ip_scope, 20, 900) or self.rate_limited(db, email_scope, 8, 900):
                return self.send_json(HTTPStatus.TOO_MANY_REQUESTS,
                                      {"error": "Too many sign-in attempts. Please wait 15 minutes and try again."})
            self.record_auth_attempt(db, ip_scope)
            self.record_auth_attempt(db, email_scope)
            user = db.execute("SELECT id,email,password_hash FROM users WHERE email=?", (email,)).fetchone()
            password_ok = verify_password(password, user["password_hash"] if user else DUMMY_HASH)
            if not user or not password_ok:
                return self.send_json(HTTPStatus.UNAUTHORIZED, {"error": "Email or password is incorrect."})
            db.execute("DELETE FROM auth_attempts WHERE scope_hash=?", (email_scope,))
            cookie = self.create_session(db, user["id"])
            workspace = db.execute("SELECT w.name FROM workspace_members m JOIN workspaces w ON w.id=m.workspace_id "
                                   "WHERE m.user_id=? ORDER BY w.id LIMIT 1", (user["id"],)).fetchone()
        return self.send_json(HTTPStatus.OK, {"id": user["id"], "email": user["email"],
                                              "workspace": workspace["name"] if workspace else "My startup"},
                              {"Set-Cookie": cookie})

    def logout(self):
        token = self.request_cookie()
        if token:
            with connect() as db:
                db.execute("DELETE FROM sessions WHERE token_hash=?", (token_digest(token),))
        return self.send_json(HTTPStatus.OK, {"ok": True},
                              {"Set-Cookie": f"{COOKIE_NAME}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"})

    def delete_account(self, data):
        password = str(data.get("password", ""))
        confirmation = str(data.get("confirmation", ""))
        with connect() as db:
            user = self.current_user(db)
            if not user:
                return self.send_json(HTTPStatus.UNAUTHORIZED, {"error": "Please sign in again before deleting your account."})
            email_scope = self.auth_scope("login-email:" + user["email"].lower())
            ip_scope = self.auth_scope("login-ip:" + (self.client_address[0] if self.client_address else "unknown"))
            if self.rate_limited(db, ip_scope, 20, 900) or self.rate_limited(db, email_scope, 8, 900):
                return self.send_json(HTTPStatus.TOO_MANY_REQUESTS, {"error": "Too many attempts. Please wait 15 minutes."})
            self.record_auth_attempt(db, ip_scope)
            self.record_auth_attempt(db, email_scope)
            db.commit()
            row = db.execute("SELECT password_hash FROM users WHERE id=?", (user["id"],)).fetchone()
            if not row or not verify_password(password, row["password_hash"]):
                return self.send_json(HTTPStatus.UNAUTHORIZED, {"error": "Password could not be verified. No data was deleted."})
            if confirmation != "DELETE":
                return self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Type DELETE to confirm account removal."})
            db.execute("DELETE FROM users WHERE id=?", (user["id"],))
            db.execute("DELETE FROM auth_attempts WHERE scope_hash=?", (email_scope,))
            db.commit()
            if not DATABASE_URL:
                db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        secure = "; Secure" if self.headers.get("X-Forwarded-Proto") == "https" else ""
        cookie = f"{COOKIE_NAME}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0{secure}"
        return self.send_json(HTTPStatus.OK, {"ok": True, "message": "Account data has been deleted."}, {"Set-Cookie": cookie})

    def save_profile(self, data):
        with connect() as db:
            user = self.current_user(db)
            if not user:
                return self.send_json(HTTPStatus.UNAUTHORIZED, {"error": "Please sign in."})
            fields = {"company", "stage", "icp", "pain", "alt", "diff", "value", "category",
                      "arpa", "margin", "cac", "churn", "payback", "ratio", "channels", "completedAt"}
            values = {key: data.get(key) for key in fields}
            workspace_name = str(values["company"] or user["workspace_name"]).strip()[:100] or user["workspace_name"]
            db.execute("UPDATE workspaces SET name=? WHERE id=?", (workspace_name, user["workspace_id"]))
            number_fields = ["arpa", "margin", "cac", "churn", "payback", "ratio"]
            try:
                numbers = {key: (None if values[key] in (None, "") else float(values[key])) for key in number_fields}
            except (TypeError, ValueError):
                return self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Financial values must be numbers."})
            if any(v is not None and (v < 0 or v > 1_000_000_000) for v in numbers.values()):
                return self.send_json(HTTPStatus.BAD_REQUEST, {"error": "A financial value is outside the allowed range."})
            channels = values["channels"] if isinstance(values["channels"], list) else []
            channels = [str(x)[:100] for x in channels[:10]]
            db.execute("""UPDATE startup_profiles SET workspace_id=?,startup_stage=?,best_fit_customer=?,customer_pain=?,
                current_alternative=?,differentiator=?,customer_value=?,market_category=?,monthly_revenue_per_customer=?,
                gross_margin_percent=?,cac_limit=?,monthly_churn_percent=?,payback_months=?,ltv_cac_target=?,
                channel_candidates=?,completed_at=?,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE user_id=?""",
                (user["workspace_id"], str(values["stage"] or "")[:200], str(values["icp"] or "")[:4000],
                 str(values["pain"] or "")[:4000], str(values["alt"] or "")[:4000], str(values["diff"] or "")[:4000],
                 str(values["value"] or "")[:4000], str(values["category"] or "")[:300], numbers["arpa"],
                 numbers["margin"], numbers["cac"], numbers["churn"], numbers["payback"], numbers["ratio"],
                 json.dumps(channels), str(values["completedAt"] or "")[:40] or None, user["id"]))
        return self.send_json(HTTPStatus.OK, {"ok": True, "workspace": workspace_name})

    def add_experiment(self, data):
        name = str(data.get("name", "")).strip()
        channel = str(data.get("channel", "Other"))[:100]
        status = str(data.get("status", "Idea"))
        hypothesis = str(data.get("hypothesis", ""))[:4000]
        review_date = str(data.get("review_date", ""))[:10] or None
        if not name or len(name) > 200:
            return self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Enter an experiment name under 200 characters."})
        if status not in {"Idea", "Running", "Check results", "Complete"}:
            return self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Choose a valid experiment status."})
        try:
            cost = None if data.get("cost_limit") in (None, "") else float(data["cost_limit"])
            if cost is not None and (cost < 0 or cost > 1_000_000_000):
                raise ValueError
        except (ValueError, TypeError):
            return self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Enter a valid spending limit."})
        with connect() as db:
            user = self.current_user(db)
            if not user:
                return self.send_json(HTTPStatus.UNAUTHORIZED, {"error": "Please sign in."})
            cur = db.execute("INSERT INTO experiments(workspace_id,created_by,name,channel,status,hypothesis,cost_limit,review_date) "
                             "VALUES(?,?,?,?,?,?,?,?)", (user["workspace_id"], user["id"], name, channel, status,
                                                           hypothesis, cost, review_date))
            row = db.execute("SELECT id,name,channel,status,hypothesis,cost_limit,review_date,created_at "
                             "FROM experiments WHERE id=?", (cur.lastrowid,)).fetchone()
        return self.send_json(HTTPStatus.CREATED, {"experiment": dict(row)})

    def add_interview(self, data):
        recent_event = str(data.get("recent_event", "")).strip()
        commitment = str(data.get("commitment", "None yet")).strip()[:200]
        if not recent_event or len(recent_event) > 4000:
            return self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Add a recent customer story under 4,000 characters."})
        with connect() as db:
            user = self.current_user(db)
            if not user:
                return self.send_json(HTTPStatus.UNAUTHORIZED, {"error": "Please sign in."})
            cur = db.execute("INSERT INTO customer_interviews(workspace_id,created_by,recent_event,commitment) VALUES(?,?,?,?)",
                             (user["workspace_id"], user["id"], recent_event, commitment))
            row = db.execute("SELECT id,recent_event,commitment,created_at FROM customer_interviews WHERE id=?",
                             (cur.lastrowid,)).fetchone()
        return self.send_json(HTTPStatus.CREATED, {"interview": dict(row)})


def retention_worker():
    """Purge expired session records and short-lived abuse-prevention counters."""
    while True:
        try:
            now = datetime.now(timezone.utc).isoformat()
            auth_cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
            with connect() as db:
                db.execute("DELETE FROM sessions WHERE expires_at<=?", (now,))
                db.execute("DELETE FROM auth_attempts WHERE attempted_at<?", (auth_cutoff,))
        except DB_ERROR as exc:
            print(f"Retention cleanup will retry: {exc}")
        time.sleep(60)


if __name__ == "__main__":
    initialize()
    Thread(target=retention_worker, name="m4s-retention", daemon=True).start()
    host = os.environ.get("M4S_HOST", "127.0.0.1")
    port = int(os.environ.get("M4S_PORT", "8000"))
    print(f"Marketing4Startups running at http://{host}:{port}")
    try:
        ThreadingHTTPServer((host, port), AppHandler).serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")

