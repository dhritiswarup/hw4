"""Campus Customs API. Run from backend/:  uvicorn main:app --reload --port 8000

- Products + images (Problem 3)
- Create account / log in with salted PBKDF2 hashes and server-side sessions (Problem 4, "Accounts" section)
- Shop chatbot backed by the PydanticAI agent (Problem 5, see agent.py / tools.py / models.py / prompts/prompt.md)
- Customer memory + page context for the chatbot (Problem 8)
- Safety guards + append-only audit trail output/audit_trail.json (Problem 12, see agent.py)

Passwords are never stored or logged. `users.password_hash` holds one of:
  pbkdf2_sha256$<iterations>$<salt>$<hex digest>   (new accounts, 600k iterations)
  pbkdf2_sha256$<salt>$<hex digest>                (seed users, 120k iterations; upgraded on next login)
The browser only holds a random session token in an HttpOnly cookie; the database stores the token's
SHA-256, so a leaked DB cannot be replayed as sessions.
"""

import hashlib
import hmac
import json
import logging
import re
import secrets
import sqlite3
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field, field_validator

from agent import AgentUnavailable, redact_sensitive, run_chat
from models import (
    ChatReply,
    ChatRequest,
    ChatTurn,
    CurrentPage,
    CustomerProfile,
    PageContext,
    Product,
    ProductDetail,
    ProductInfo,
    ShopDeps,
)
from tools import DATA_DIR, DB_PATH, as_product, get_product_info, load_product, load_products, product_cards

log = logging.getLogger("campus_customs")

# The course data pack is local-only (not in git). Fail fast with instructions instead of a cryptic error.
if not DB_PATH.is_file() or not (DATA_DIR / "products").is_dir():
    raise RuntimeError(
        f"Data pack not found. Put campus_customs.db and the products/ image folder in {DATA_DIR} "
        "(see README.md, 'Place the data pack')."
    )
CHAT_HISTORY_LIMIT = 50  # messages returned to the widget on open
MODEL_HISTORY_LIMIT = 12  # saved messages replayed to the agent each turn
SAFE_PATH = re.compile(r"^/[A-Za-z0-9_\-/]{0,199}$")
SAFE_TEXT = re.compile(r"[^A-Za-z0-9 $.,'&\-]")


# =========================================================================
# Accounts: password hashing, sessions, signup / login / logout / me (Problem 4)
# =========================================================================

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 600_000  # OWASP 2023 recommendation for PBKDF2-HMAC-SHA256
LEGACY_ITERATIONS = 120_000  # used by the seed database's 3-part hashes
SESSION_COOKIE = "cc_session"
SESSION_TTL = timedelta(days=7)
MAX_FAILED_LOGINS = 5
FAILED_LOGIN_WINDOW = 15 * 60  # seconds

auth_router = APIRouter(prefix="/api/auth", tags=["auth"])


# ---------- password hashing ----------

def _pbkdf2(password: str, salt: str, iterations: int) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations).hex()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    return f"{ALGORITHM}${ITERATIONS}${salt}${_pbkdf2(password, salt, ITERATIONS)}"


def _parse_hash(stored: str) -> tuple[int, str, str] | None:
    parts = stored.split("$")
    if parts[0] != ALGORITHM:
        return None
    if len(parts) == 4 and parts[1].isdigit():
        return int(parts[1]), parts[2], parts[3]
    if len(parts) == 3:
        return LEGACY_ITERATIONS, parts[1], parts[2]
    return None


def verify_password(password: str, stored: str) -> bool:
    parsed = _parse_hash(stored)
    if parsed is None:
        return False
    iterations, salt, digest = parsed
    return hmac.compare_digest(_pbkdf2(password, salt, iterations), digest)


def needs_rehash(stored: str) -> bool:
    parsed = _parse_hash(stored)
    return parsed is None or parsed[0] < ITERATIONS


# Verified against when the email is unknown, so response time doesn't reveal which emails exist.
_DUMMY_HASH = hash_password(secrets.token_hex(16))


# ---------- brute-force throttle (in memory, per client IP + email) ----------

_failed: dict[str, deque[float]] = defaultdict(deque)


def _throttle_key(request: Request, email: str) -> str:
    host = request.client.host if request.client else "unknown"
    return f"{host}|{email}"


def _recent_failures(key: str) -> deque[float]:
    q = _failed[key]
    cutoff = time.monotonic() - FAILED_LOGIN_WINDOW
    while q and q[0] < cutoff:
        q.popleft()
    return q


# ---------- database ----------

def db_connect() -> sqlite3.Connection:
    """Read/write connection (users, sessions, chat_messages). Catalogue reads use tools.connect (read-only)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_auth_tables() -> None:
    with db_connect() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                expires_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )"""
        )
        conn.execute("DELETE FROM sessions WHERE expires_at < datetime('now')")


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _start_session(conn: sqlite3.Connection, response: Response, user_id: int) -> None:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + SESSION_TTL
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
        (_token_hash(token), user_id, expires.strftime("%Y-%m-%d %H:%M:%S")),
    )
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(SESSION_TTL.total_seconds()),
        httponly=True,  # not readable from JavaScript
        samesite="lax",  # not sent on cross-site POSTs
        secure=False,  # set True when served over HTTPS
        path="/",
    )


def current_user(token: str | None) -> sqlite3.Row | None:
    """The logged-in user for a session token, or None. Used by other routes (e.g. chat)."""
    if not token:
        return None
    with db_connect() as conn:
        return conn.execute(
            """SELECT u.id, u.first_name, u.last_name, u.name, u.email, u.created_at
               FROM sessions s JOIN users u ON u.id = s.user_id
               WHERE s.token_hash = ? AND s.expires_at > datetime('now')""",
            (_token_hash(token),),
        ).fetchone()


# ---------- API models ----------

class SignupRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=60)
    last_name: str = Field(min_length=1, max_length=60)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("first_name", "last_name")
    @classmethod
    def strip_names(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    """Public view of a user. Never includes password_hash."""

    id: int
    first_name: str
    last_name: str
    email: str


def _user_out(row: sqlite3.Row) -> UserOut:
    # Seed rows may have NULL first/last name; fall back to splitting `name`.
    first, _, last = (row["name"] or "").partition(" ")
    return UserOut(
        id=row["id"],
        first_name=row["first_name"] or first,
        last_name=row["last_name"] or last,
        email=row["email"],
    )


# ---------- routes ----------

@auth_router.post("/signup", response_model=UserOut, status_code=201)
def signup(body: SignupRequest, response: Response) -> UserOut:
    email = body.email.strip().lower()
    with db_connect() as conn:
        if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            raise HTTPException(409, "An account with that email already exists.")
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash, first_name, last_name) VALUES (?, ?, ?, ?, ?)",
            (f"{body.first_name} {body.last_name}", email, hash_password(body.password), body.first_name, body.last_name),
        )
        _start_session(conn, response, cur.lastrowid)
        row = conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _user_out(row)


@auth_router.post("/login", response_model=UserOut)
def login(body: LoginRequest, request: Request, response: Response) -> UserOut:
    email = body.email.strip().lower()
    key = _throttle_key(request, email)
    failures = _recent_failures(key)
    if len(failures) >= MAX_FAILED_LOGINS:
        raise HTTPException(429, "Too many failed attempts. Please wait a few minutes and try again.")

    with db_connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        ok = verify_password(body.password, row["password_hash"] if row else _DUMMY_HASH)
        if not row or not ok:
            failures.append(time.monotonic())
            raise HTTPException(401, "Invalid email or password.")

        failures.clear()
        if needs_rehash(row["password_hash"]):
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(body.password), row["id"]))
        _start_session(conn, response, row["id"])
    return _user_out(row)


@auth_router.post("/logout", status_code=204)
def logout(response: Response, cc_session: str | None = Cookie(default=None)) -> None:
    if cc_session:
        with db_connect() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(cc_session),))
    response.delete_cookie(SESSION_COOKIE, path="/")


@auth_router.get("/me", response_model=UserOut)
def me(cc_session: str | None = Cookie(default=None)) -> UserOut:
    row = current_user(cc_session)
    if row is None:
        raise HTTPException(401, "Not logged in.")
    return _user_out(row)


# =========================================================================
# App setup
# =========================================================================

def init_chat_table() -> None:
    """Add chat_messages.page_context (JSON: page, path, product_id, product_name) if the seed DB lacks it."""
    with db_connect() as conn:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(chat_messages)")}
        if "page_context" not in cols:
            conn.execute("ALTER TABLE chat_messages ADD COLUMN page_context TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_user ON chat_messages(user_id, id)")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_auth_tables()
    init_chat_table()
    yield


app = FastAPI(title="Campus Customs API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
# image_file_path is relative to data/ (e.g. "products/x.jpg") -> served at /media/products/x.jpg
app.mount("/media/products", StaticFiles(directory=DATA_DIR / "products"), name="products")


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    # FastAPI's default 422 echoes the submitted value back, which would include passwords.
    errors = [{"loc": e["loc"], "msg": e["msg"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})


# ---------- products ----------

@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/products", response_model=list[Product])
def list_products() -> list[Product]:
    return [as_product(p) for p in load_products()]


@app.get("/api/products/{product_id}", response_model=ProductDetail)
def get_product(product_id: str) -> ProductDetail:
    product = load_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


# ---------- chat ----------

def _load_rows(user_id: int, limit: int) -> list[sqlite3.Row]:
    """The user's most recent saved messages, oldest first."""
    with db_connect() as conn:
        rows = conn.execute(
            "SELECT role, content, products_json, page_context FROM chat_messages "
            "WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return list(reversed(rows))


def _model_history(rows: list[sqlite3.Row]) -> list[ChatTurn]:
    """Saved turns for the agent. User turns keep a note of the product page they were on, so "this" still resolves."""
    turns = []
    for r in rows:
        content = r["content"]
        page = json.loads(r["page_context"]) if r["page_context"] else {}
        if r["role"] == "user" and page.get("product_id"):
            content = f"[Shopper was viewing {page['product_name']} ({page['product_id']})] {content}"
        turns.append(ChatTurn(role=r["role"], content=content))
    return turns


def _customer(user: sqlite3.Row) -> CustomerProfile:
    with db_connect() as conn:
        saved = conn.execute("SELECT COUNT(*) FROM chat_messages WHERE user_id = ?", (user["id"],)).fetchone()[0]
    first, _, last = (user["name"] or "").partition(" ")
    return CustomerProfile(
        user_id=user["id"],
        first_name=user["first_name"] or first,
        last_name=user["last_name"] or last,
        email=user["email"],
        member_since=(user["created_at"] or "")[:10],
        saved_messages=saved,
    )


def _current_page(ctx: PageContext | None) -> CurrentPage | None:
    """Resolve the widget's (untrusted) page context: validate the path, look the product up in the DB."""
    if ctx is None:
        return None
    product = get_product_info(ctx.product_id) if ctx.product_id else None
    title = SAFE_TEXT.sub("", ctx.results_title or "")[:60].strip()
    return CurrentPage(
        page=ctx.page,
        path=ctx.path if SAFE_PATH.match(ctx.path) else "/",
        product=product if isinstance(product, ProductInfo) else None,
        results_title=title or None,
        results_filters=[SAFE_TEXT.sub("", f)[:30] for f in ctx.results_filters if f],
        preferred_size=ctx.preferred_size,  # already validated against XS-XXL by PageContext
    )


def _save_turns(user_id: int, message: str, reply: ChatReply, page: CurrentPage | None) -> None:
    products_json = json.dumps([c.model_dump() for c in reply.products]) if reply.products else None
    page_json = None
    if page:
        page_json = json.dumps({
            "page": page.page,
            "path": page.path,
            "product_id": page.product.product_id if page.product else None,
            "product_name": page.product.name if page.product else None,
        })
    with db_connect() as conn:
        conn.execute(
            "INSERT INTO chat_messages (user_id, role, content, page_context) VALUES (?, 'user', ?, ?)",
            (user_id, message, page_json),
        )
        conn.execute(
            "INSERT INTO chat_messages (user_id, role, content, products_json) VALUES (?, 'assistant', ?, ?)",
            (user_id, reply.content, products_json),
        )


@app.post("/api/chat", response_model=ChatReply)
async def chat(body: ChatRequest, cc_session: str | None = Cookie(default=None)) -> ChatReply:
    user = current_user(cc_session)
    # Card numbers / passwords / SSNs are removed before the model, the database or the audit log see them.
    message, _ = redact_sensitive(body.message.strip())
    if not message:
        raise HTTPException(422, "Message is empty.")

    # Who is chatting comes only from the session cookie; where they are comes from the widget (validated).
    deps = ShopDeps(customer=_customer(user) if user else None, page=_current_page(body.page))
    # Logged-in shoppers: history comes from the database (trusted, per user). Guests: from the widget.
    if user:
        history = _model_history(_load_rows(user["id"], MODEL_HISTORY_LIMIT))
    else:
        history = [ChatTurn(role=t.role, content=redact_sensitive(t.content)[0]) for t in body.history]

    # run_chat handles usage limits and the provider content filter itself and audits every run.
    try:
        reply = await run_chat(message, history, deps)
    except AgentUnavailable:
        raise HTTPException(502, "The assistant is having trouble right now. Please try again in a moment.")

    if user:
        _save_turns(user["id"], message, reply, deps.page)
    return reply


@app.get("/api/chat/history", response_model=list[ChatReply])
def chat_history(cc_session: str | None = Cookie(default=None)) -> list[ChatReply]:
    """The logged-in shopper's saved conversation (empty for guests). Cards are refreshed with live stock."""
    user = current_user(cc_session)
    if not user:
        return []
    replies = []
    for r in _load_rows(user["id"], CHAT_HISTORY_LIMIT):
        ids = [p["product_id"] for p in json.loads(r["products_json"])] if r["products_json"] else []
        replies.append(ChatReply(role=r["role"], content=r["content"], products=product_cards(ids)))
    return replies


@app.delete("/api/chat/history", status_code=204)
def clear_chat_history(cc_session: str | None = Cookie(default=None)) -> None:
    """Let a logged-in shopper erase their own saved conversation (the agent's memory of them)."""
    user = current_user(cc_session)
    if not user:
        raise HTTPException(401, "Not logged in.")
    with db_connect() as conn:
        conn.execute("DELETE FROM chat_messages WHERE user_id = ?", (user["id"],))
