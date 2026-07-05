# WheelHive Web Companion — Implementation Plan (Phase 0 + 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a single-user, auth'd FastAPI companion web app on `wheelhive-vm` that serves a React SPA showing an interactive positions dashboard (stock holdings + open options + portfolio summary tiles), reusing WheelHive's existing domain library.

**Architecture:** A new `src/web` FastAPI app, run as its own `wheelhive-web.service` (uvicorn `:8080`, own lean venv), imports the existing domain modules (`Positions`, `DFStats`, `Db`) directly against the shared `trades.db` (WAL). Session-cookie auth for a single user. A Vite + React + TypeScript SPA (AG Grid Community) is built on the Mac and served as static files by the same app.

**Tech Stack:** Python ≥3.10, FastAPI, uvicorn, Starlette SessionMiddleware; Vite + React + TypeScript + AG Grid Community; SQLite (shared `trades.db`).

## Global Constraints

- Python ≥3.10 (target 3.10–3.13). Copy the codebase's existing style.
- Backend imports domain modules as top-level names (e.g. `from positions import Positions`) with `src/` on `sys.path` — matches how `bot.py`/`cli.py` run. Run the app from within `src/`.
- The web venv (`.web_venv`) MUST NOT install `discord.py`, `torch`, `easyocr`, or `chromadb`. It needs: `fastapi`, `uvicorn[standard]`, `itsdangerous` (SessionMiddleware), plus the data-path deps already required by the domain layer (`pandas`, `numpy`, `scipy`, `yfinance`, `pandas-ta`).
- Single user: the owner's username is fixed via env `WHEELHIVE_WEB_USERNAME` (value: `sangelovich`). No user picker.
- DB path from env `WHEELHIVE_WEB_DB` (default `/home/steve/code/wheelhive/trades.db`).
- Server binds `0.0.0.0:8080`. Access is LAN-restricted via ufw (`192.168.68.0/22`) + session auth.
- Secrets from `.env`: `WHEELHIVE_WEB_PASSWORD`, `WHEELHIVE_WEB_SECRET`. Never commit them.
- Frontend build output goes to `src/web/static/` (served by FastAPI). No Node runtime on the VM.

---

## File Structure

**Create:**
- `src/guild_objects.py` — discord.Object-wrapped guild id lists (the only discord-dependent constants).
- `src/web/__init__.py`
- `src/web/config.py` — env-driven settings.
- `src/web/auth.py` — session login/logout + `require_auth` dependency.
- `src/web/deps.py` — per-request `Db`/`Positions`/`DFStats` providers + accounts helper.
- `src/web/routes/__init__.py`
- `src/web/routes/positions.py` — `/api/accounts`, `/api/positions`, `/api/portfolio/summary`.
- `src/web/app.py` — app factory: middleware, routes, static mount.
- `src/web/static/.gitkeep` — placeholder; React build lands here.
- `tests/test_constants_no_discord.py`
- `tests/web/__init__.py`, `tests/web/test_auth.py`, `tests/web/test_positions_api.py`, `tests/web/conftest.py`
- `web-ui/` — Vite React TS project (see Task 9 for files).
- `deploy/wheelhive-web.service`

**Modify:**
- `src/constants.py` — remove `import discord` and the `GUILD_IDS`/`DEV_GUILD_IDS` wrapping; keep raw int lists + `ALLOWED_GUILD_IDS`.
- `src/bot.py` — import `GUILD_IDS`/`DEV_GUILD_IDS` from `guild_objects` instead of `constants`.

---

## Phase 0 — Decouple discord from constants

### Task 1: Split discord.Object guild ids out of constants.py

**Files:**
- Create: `src/guild_objects.py`
- Modify: `src/constants.py` (remove `import discord` at line 13; remove `GUILD_IDS`/`DEV_GUILD_IDS` blocks ~149-157)
- Modify: `src/bot.py` (imports of `GUILD_IDS`, `DEV_GUILD_IDS`)
- Test: `tests/test_constants_no_discord.py`

**Interfaces:**
- Produces: `constants.GUILDS: list[int]`, `constants.DEV_GUILDS: list[int]`, `constants.ALLOWED_GUILD_IDS: set[int]` (no discord import). `guild_objects.GUILD_IDS: list[discord.Object]`, `guild_objects.DEV_GUILD_IDS: list[discord.Object]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_constants_no_discord.py
import ast, pathlib

CONST = pathlib.Path(__file__).parent.parent / "src" / "constants.py"

def test_constants_does_not_import_discord():
    tree = ast.parse(CONST.read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "discord" not in imported, "constants.py must not import discord"

def test_constants_guild_values():
    import sys
    sys.path.insert(0, str(CONST.parent))
    import constants
    assert constants.GUILDS == [1349592236375019520]
    assert constants.DEV_GUILDS == [1349592236375019520]
    assert constants.ALLOWED_GUILD_IDS == {1349592236375019520}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/steve/code/wheelhive && .venv/bin/python -m pytest tests/test_constants_no_discord.py -v`
Expected: `test_constants_does_not_import_discord` FAILS (discord is imported).

- [ ] **Step 3: Create `src/guild_objects.py`**

```python
"""Discord-object-wrapped guild id lists. Isolated here so non-Discord
processes (e.g. the web app) can import `constants` without discord.py."""
import discord

from constants import DEV_GUILDS, GUILDS

GUILD_IDS = [discord.Object(id=i) for i in GUILDS]
DEV_GUILD_IDS = [discord.Object(id=i) for i in DEV_GUILDS]
```

- [ ] **Step 4: Edit `src/constants.py`** — delete `import discord` (line 13) and the two `*_GUILD_IDS` loops, leaving:

```python
# DEV GUILD IDs
DEV_GUILDS = [1349592236375019520]

# Production Guild IDs — locked to the owner's personal server only.
GUILDS = [1349592236375019520]

# The only guilds this bot may operate in.
ALLOWED_GUILD_IDS = set(GUILDS) | set(DEV_GUILDS)
```

- [ ] **Step 5: Update `src/bot.py`** — change `from constants import ... GUILD_IDS ...` usages. Add near the other imports:

```python
from guild_objects import GUILD_IDS, DEV_GUILD_IDS
```
and remove `GUILD_IDS`/`DEV_GUILD_IDS` from the `constants` import if present (grep `const.GUILD_IDS` / `const.DEV_GUILD_IDS` and repoint to the new module, or import as above and replace `const.GUILD_IDS`→`GUILD_IDS`).

- [ ] **Step 6: Run tests**

Run: `cd /home/steve/code/wheelhive && .venv/bin/python -m pytest tests/test_constants_no_discord.py -v`
Expected: PASS. Then `.bot_venv/bin/python -c "import sys; sys.path.insert(0,'src'); import bot"` should still import cleanly.

- [ ] **Step 7: Commit**

```bash
git add src/guild_objects.py src/constants.py src/bot.py tests/test_constants_no_discord.py
git commit -m "refactor: isolate discord.Object guild ids so constants is discord-free"
```

---

## Phase 1a — Backend

### Task 2: Web config module

**Files:** Create `src/web/__init__.py` (empty), `src/web/config.py`

**Interfaces:**
- Produces: `config.settings` with attrs `username: str`, `db_path: str`, `password: str`, `secret: str`.

- [ ] **Step 1: Write `src/web/config.py`**

```python
import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    username: str
    db_path: str
    password: str
    secret: str

def load_settings() -> Settings:
    return Settings(
        username=os.environ.get("WHEELHIVE_WEB_USERNAME", "sangelovich"),
        db_path=os.environ.get("WHEELHIVE_WEB_DB", "/home/steve/code/wheelhive/trades.db"),
        password=os.environ.get("WHEELHIVE_WEB_PASSWORD", ""),
        secret=os.environ.get("WHEELHIVE_WEB_SECRET", ""),
    )

settings = load_settings()
```

- [ ] **Step 2: Commit**

```bash
git add src/web/__init__.py src/web/config.py
git commit -m "feat(web): web app config from env"
```

### Task 3: Session auth

**Files:** Create `src/web/auth.py`; Test `tests/web/__init__.py`, `tests/web/conftest.py`, `tests/web/test_auth.py`

**Interfaces:**
- Consumes: `config.settings`.
- Produces: `auth.router` (APIRouter with `POST /api/login`, `POST /api/logout`, `GET /api/session`); `auth.require_auth(request)` FastAPI dependency raising 401 if not authed.

- [ ] **Step 1: Write `tests/web/conftest.py`**

```python
import os
os.environ.setdefault("WHEELHIVE_WEB_PASSWORD", "testpw")
os.environ.setdefault("WHEELHIVE_WEB_SECRET", "test-secret-key")
```

- [ ] **Step 2: Write the failing test `tests/web/test_auth.py`**

```python
from fastapi.testclient import TestClient
from web.app import create_app

def client():
    return TestClient(create_app())

def test_session_unauthed():
    r = client().get("/api/session")
    assert r.status_code == 200
    assert r.json() == {"authenticated": False}

def test_login_wrong_password():
    r = client().post("/api/login", json={"password": "nope"})
    assert r.status_code == 401

def test_login_then_session_ok():
    c = client()
    assert c.post("/api/login", json={"password": "testpw"}).status_code == 200
    assert c.get("/api/session").json() == {"authenticated": True}

def test_protected_requires_auth():
    r = client().get("/api/accounts")
    assert r.status_code == 401
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd src && ../.web_venv/bin/python -m pytest ../tests/web/test_auth.py -v`
Expected: FAIL (`web.app` not importable yet). Tasks 3–8 make these pass together; expect red until Task 8.

- [ ] **Step 4: Write `src/web/auth.py`**

```python
import hmac
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from web.config import settings

router = APIRouter()

class LoginBody(BaseModel):
    password: str

def require_auth(request: Request) -> None:
    if not request.session.get("authed"):
        raise HTTPException(status_code=401, detail="authentication required")

@router.post("/api/login")
def login(body: LoginBody, request: Request):
    if not settings.password or not hmac.compare_digest(body.password, settings.password):
        raise HTTPException(status_code=401, detail="invalid password")
    request.session["authed"] = True
    return {"authenticated": True}

@router.post("/api/logout")
def logout(request: Request):
    request.session.clear()
    return {"authenticated": False}

@router.get("/api/session")
def session(request: Request):
    return {"authenticated": bool(request.session.get("authed"))}
```

- [ ] **Step 5: Commit** (tests still red until Task 8 wires the app)

```bash
git add src/web/auth.py tests/web/__init__.py tests/web/conftest.py tests/web/test_auth.py
git commit -m "feat(web): session auth (login/logout/session + require_auth)"
```

### Task 4: DB/domain providers

**Files:** Create `src/web/deps.py`

**Interfaces:**
- Produces:
  - `get_db() -> Db` — opens `Db` at `settings.db_path`.
  - `get_positions(db) -> Positions` — `Positions(db, Shares(db), Trades(db))`.
  - `list_accounts(db, username) -> list[str]` — distinct accounts across trades/shares/deposits/dividends, `default` first.

- [ ] **Step 1: Write `src/web/deps.py`**

```python
from db import Db
from shares import Shares
from trades import Trades
from positions import Positions
from web.config import settings

def get_db() -> Db:
    return Db(db_path=settings.db_path) if _accepts_path() else Db()

def _accepts_path() -> bool:
    import inspect
    return "db_path" in inspect.signature(Db.__init__).parameters

def get_positions(db: Db) -> Positions:
    return Positions(db, Shares(db), Trades(db))

def list_accounts(db: Db, username: str) -> list[str]:
    sql = """
      SELECT DISTINCT account FROM (
        SELECT account FROM trades    WHERE username=?
        UNION SELECT account FROM shares    WHERE username=?
        UNION SELECT account FROM deposits  WHERE username=?
        UNION SELECT account FROM dividends WHERE username=?
      ) WHERE account IS NOT NULL
    """
    rows = db.query_parameterized(sql, (username, username, username, username))
    accounts = sorted({r[0] for r in rows})
    if "default" in accounts:
        accounts.remove("default"); accounts.insert(0, "default")
    return accounts
```

> Note: verify `Db.__init__` signature in `src/db.py`; if it takes no `db_path`, set the DB path via whatever mechanism `constants.PROJECT_ROOT`/`DATABASE_PATH` uses (env `WHEELHIVE_WEB_DB` should point the process at the right file). The `_accepts_path` guard keeps this robust.

- [ ] **Step 2: Commit**

```bash
git add src/web/deps.py
git commit -m "feat(web): db/domain providers + account lister"
```

### Task 5: Accounts endpoint

**Files:** Create `src/web/routes/__init__.py` (empty), `src/web/routes/positions.py`; Test extends `tests/web/test_positions_api.py`

**Interfaces:**
- Produces: `positions.router` with `GET /api/accounts` → `{"accounts": list[str], "username": str}` (auth required).

- [ ] **Step 1: Write the failing test `tests/web/test_positions_api.py`**

```python
from fastapi.testclient import TestClient
from web.app import create_app

def authed_client():
    c = TestClient(create_app())
    c.post("/api/login", json={"password": "testpw"})
    return c

def test_accounts_shape():
    r = authed_client().get("/api/accounts")
    assert r.status_code == 200
    body = r.json()
    assert "accounts" in body and isinstance(body["accounts"], list)
    assert body["username"]
```

- [ ] **Step 2: Write `src/web/routes/positions.py` (accounts route first)**

```python
from fastapi import APIRouter, Depends, Query
from web.auth import require_auth
from web.config import settings
from web import deps

router = APIRouter(prefix="/api", dependencies=[Depends(require_auth)])

@router.get("/accounts")
def accounts():
    db = deps.get_db()
    return {"username": settings.username,
            "accounts": deps.list_accounts(db, settings.username)}
```

- [ ] **Step 3: Commit**

```bash
git add src/web/routes/__init__.py src/web/routes/positions.py tests/web/test_positions_api.py
git commit -m "feat(web): /api/accounts endpoint"
```

### Task 6: Positions endpoint

**Files:** Modify `src/web/routes/positions.py`; Test extends `tests/web/test_positions_api.py`

**Interfaces:**
- Produces: `GET /api/positions?account=<str>` → `{"account": str|None, "stocks": list[dict], "options": list[dict]}` from `Positions.get_stock_positions` / `get_open_options`.

- [ ] **Step 1: Add the failing test**

```python
def test_positions_shape():
    r = authed_client().get("/api/positions")
    assert r.status_code == 200
    body = r.json()
    assert set(body) >= {"stocks", "options", "account"}
    assert isinstance(body["stocks"], list) and isinstance(body["options"], list)
```

- [ ] **Step 2: Add the route to `src/web/routes/positions.py`**

```python
@router.get("/positions")
def positions(account: str | None = Query(default=None)):
    db = deps.get_db()
    pos = deps.get_positions(db)
    acct = account or None
    return {
        "account": acct,
        "stocks": pos.get_stock_positions(settings.username, acct),
        "options": pos.get_open_options(settings.username, acct),
    }
```

- [ ] **Step 3: Run tests / Commit**

Run (after Task 8 app exists): `cd src && ../.web_venv/bin/python -m pytest ../tests/web -v`
```bash
git add src/web/routes/positions.py tests/web/test_positions_api.py
git commit -m "feat(web): /api/positions endpoint (stocks + open options)"
```

### Task 7: Portfolio summary endpoint

**Files:** Modify `src/web/routes/positions.py`; Test extends `tests/web/test_positions_api.py`

**Interfaces:**
- Produces: `GET /api/portfolio/summary?account=&year=` → `{"account", "year", "options": dict, "dividends": dict, "stocks_unrealized": float}` where `options`/`dividends` come from `DFStats`, and `stocks_unrealized` sums `unrealized P/L` from `get_stock_positions`.

- [ ] **Step 1: Add the failing test**

```python
def test_summary_shape():
    r = authed_client().get("/api/portfolio/summary")
    assert r.status_code == 200
    body = r.json()
    assert set(body) >= {"options", "dividends", "stocks_unrealized", "year", "account"}
```

- [ ] **Step 2: Add the route** (import `DFStats`, `datetime` at top of file)

```python
from datetime import date
from df_stats import DFStats

@router.get("/portfolio/summary")
def summary(account: str | None = Query(default=None), year: int | None = Query(default=None)):
    db = deps.get_db()
    yr = year or date.today().year
    stats = DFStats(db)
    stats.load(username=settings.username, account=account)
    stats.filter_by_year(yr)
    stats_dict = stats.as_dict()
    pos = deps.get_positions(db)
    stocks = pos.get_stock_positions(settings.username, account or None)
    unreal = 0.0
    for s in stocks:
        for k in ("unrealized_pl", "unrealized_pnl", "unrealized"):
            if k in s and isinstance(s[k], (int, float)):
                unreal += float(s[k]); break
    return {
        "account": account or None,
        "year": yr,
        "options": stats_dict.get("options", stats_dict),
        "dividends": stats_dict.get("dividends", {}),
        "stocks_unrealized": round(unreal, 2),
    }
```

> Note: inspect `DFStats.as_dict()` output keys in `src/df_stats.py:238` and the exact unrealized-P/L key in a `get_stock_positions` dict (`src/positions.py:136`); adjust the key lookups above to the real names during implementation.

- [ ] **Step 3: Commit**

```bash
git add src/web/routes/positions.py tests/web/test_positions_api.py
git commit -m "feat(web): /api/portfolio/summary endpoint"
```

### Task 8: App assembly + static serving

**Files:** Create `src/web/app.py`, `src/web/static/.gitkeep`

**Interfaces:**
- Produces: `app.create_app() -> FastAPI` with SessionMiddleware, auth router, positions router, and `/` serving `static/index.html` (SPA) when built.

- [ ] **Step 1: Write `src/web/app.py`**

```python
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from web.config import settings
from web.auth import router as auth_router
from web.routes.positions import router as positions_router

STATIC = Path(__file__).parent / "static"

def create_app() -> FastAPI:
    app = FastAPI(title="WheelHive Web")
    app.add_middleware(SessionMiddleware, secret_key=settings.secret or "dev-insecure",
                       same_site="lax", https_only=False)
    app.include_router(auth_router)
    app.include_router(positions_router)

    @app.get("/health")
    def health():
        return {"ok": True}

    if (STATIC / "index.html").exists():
        app.mount("/", StaticFiles(directory=str(STATIC), html=True), name="spa")
    return app

app = create_app()

def main():
    import uvicorn
    uvicorn.run("web.app:app", host="0.0.0.0", port=8080, log_level="info")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create the web venv and run the whole backend test suite**

```bash
cd /home/steve/code/wheelhive
python3 -m venv .web_venv
.web_venv/bin/pip install fastapi "uvicorn[standard]" itsdangerous httpx pytest \
  pandas numpy scipy yfinance pandas-ta
cd src && ../.web_venv/bin/python -m pytest ../tests/web -v
```
Expected: all tests in `tests/web` PASS.

- [ ] **Step 3: Smoke-run locally**

```bash
cd /home/steve/code/wheelhive/src
WHEELHIVE_WEB_PASSWORD=dev WHEELHIVE_WEB_SECRET=dev ../.web_venv/bin/python -m web.app &
curl -s localhost:8080/health          # {"ok":true}
curl -s -c /tmp/cj -X POST localhost:8080/api/login -H 'content-type: application/json' -d '{"password":"dev"}'
curl -s -b /tmp/cj localhost:8080/api/accounts
kill %1
```

- [ ] **Step 4: Commit**

```bash
git add src/web/app.py src/web/static/.gitkeep
git commit -m "feat(web): FastAPI app assembly + SPA static mount"
```

---

## Phase 1b — Frontend (Vite + React + TS + AG Grid)

### Task 9: Scaffold the SPA

**Files:** Create `web-ui/` (Vite project). Build output → `src/web/static/`.

- [ ] **Step 1: Scaffold on the Mac**

```bash
cd /Users/steve/code/wheelhive-bot
npm create vite@latest web-ui -- --template react-ts
cd web-ui && npm install && npm install ag-grid-react ag-grid-community
```

- [ ] **Step 2: Set `web-ui/vite.config.ts`** to build into the backend static dir and proxy `/api` in dev:

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  build: { outDir: "../src/web/static", emptyOutDir: true },
  server: { proxy: { "/api": "http://localhost:8080" } },
});
```

- [ ] **Step 3: Add API client `web-ui/src/api.ts`**

```ts
async function j(path: string, opts: RequestInit = {}) {
  const r = await fetch(path, { credentials: "include", headers: { "content-type": "application/json" }, ...opts });
  if (r.status === 401) throw new Error("unauthorized");
  if (!r.ok) throw new Error(`${path} ${r.status}`);
  return r.json();
}
export const api = {
  session: () => j("/api/session"),
  login: (password: string) => j("/api/login", { method: "POST", body: JSON.stringify({ password }) }),
  logout: () => j("/api/logout", { method: "POST" }),
  accounts: () => j("/api/accounts"),
  positions: (account?: string) => j(`/api/positions${account ? `?account=${encodeURIComponent(account)}` : ""}`),
  summary: (account?: string) => j(`/api/portfolio/summary${account ? `?account=${encodeURIComponent(account)}` : ""}`),
};
```

- [ ] **Step 4: Commit**

```bash
git add web-ui
git commit -m "feat(web-ui): scaffold Vite React TS app + AG Grid + api client"
```

### Task 10: Login gate

**Files:** Create `web-ui/src/Login.tsx`; modify `web-ui/src/App.tsx`.

- [ ] **Step 1: `web-ui/src/Login.tsx`**

```tsx
import { useState } from "react";
import { api } from "./api";
export function Login({ onOk }: { onOk: () => void }) {
  const [pw, setPw] = useState(""); const [err, setErr] = useState("");
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    try { await api.login(pw); onOk(); } catch { setErr("Invalid password"); }
  };
  return (
    <form onSubmit={submit} style={{ maxWidth: 320, margin: "20vh auto", display: "grid", gap: 8 }}>
      <h2>WheelHive</h2>
      <input type="password" value={pw} onChange={e => setPw(e.target.value)} placeholder="Password" autoFocus />
      <button type="submit">Sign in</button>
      {err && <span style={{ color: "crimson" }}>{err}</span>}
    </form>
  );
}
```

- [ ] **Step 2: Gate in `web-ui/src/App.tsx`** — on mount call `api.session()`; render `<Login>` if not authed, else `<Dashboard>` (Task 11). Commit.

```bash
git add web-ui/src/Login.tsx web-ui/src/App.tsx
git commit -m "feat(web-ui): login gate + session check"
```

### Task 11: Positions dashboard

**Files:** Create `web-ui/src/Dashboard.tsx`, `web-ui/src/Grids.tsx`.

- [ ] **Step 1: `web-ui/src/Grids.tsx`** — two AG Grid tables with auto column defs from row keys:

```tsx
import { AgGridReact } from "ag-grid-react";
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-quartz.css";
export function Grid({ rows }: { rows: Record<string, unknown>[] }) {
  const cols = rows.length ? Object.keys(rows[0]).map(f => ({ field: f, sortable: true, filter: true, resizable: true })) : [];
  return <div className="ag-theme-quartz-dark" style={{ height: 340, width: "100%" }}>
    <AgGridReact rowData={rows} columnDefs={cols} />
  </div>;
}
```

- [ ] **Step 2: `web-ui/src/Dashboard.tsx`** — account switcher + Refresh + summary tiles + two grids:

```tsx
import { useEffect, useState } from "react";
import { api } from "./api";
import { Grid } from "./Grids";
export function Dashboard() {
  const [accounts, setAccounts] = useState<string[]>([]);
  const [acct, setAcct] = useState<string | undefined>();
  const [pos, setPos] = useState<{ stocks: any[]; options: any[] }>({ stocks: [], options: [] });
  const [sum, setSum] = useState<any>(null);
  const load = async () => { setPos(await api.positions(acct)); setSum(await api.summary(acct)); };
  useEffect(() => { api.accounts().then(a => setAccounts(a.accounts)); }, []);
  useEffect(() => { load(); }, [acct]);
  return (
    <div style={{ padding: 16 }}>
      <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
        <h2>Positions</h2>
        <select value={acct ?? ""} onChange={e => setAcct(e.target.value || undefined)}>
          <option value="">All accounts</option>
          {accounts.map(a => <option key={a} value={a}>{a}</option>)}
        </select>
        <button onClick={load}>Refresh</button>
        <button onClick={() => api.logout().then(() => location.reload())} style={{ marginLeft: "auto" }}>Sign out</button>
      </div>
      {sum && <div style={{ display: "flex", gap: 16, margin: "12px 0" }}>
        <Tile label={`YTD unrealized P/L`} value={sum.stocks_unrealized} />
        <Tile label={`Year`} value={sum.year} />
      </div>}
      <h3>Stock Holdings</h3><Grid rows={pos.stocks} />
      <h3>Open Options</h3><Grid rows={pos.options} />
    </div>
  );
}
function Tile({ label, value }: { label: string; value: unknown }) {
  return <div style={{ border: "1px solid #333", borderRadius: 8, padding: "8px 16px" }}>
    <div style={{ opacity: .7, fontSize: 12 }}>{label}</div>
    <div style={{ fontSize: 22 }}>{String(value)}</div>
  </div>;
}
```

- [ ] **Step 3: Build + verify end-to-end**

```bash
cd /Users/steve/code/wheelhive-bot/web-ui && npm run build   # outputs to ../src/web/static
cd ../ && cd src && WHEELHIVE_WEB_PASSWORD=dev WHEELHIVE_WEB_SECRET=dev ../.web_venv/bin/python -m web.app &
# open http://localhost:8080 → login with "dev" → see dashboard; kill when done
```

- [ ] **Step 4: Commit**

```bash
git add web-ui/src src/web/static
git commit -m "feat(web-ui): positions dashboard (tiles + AG Grid holdings/options + account switcher)"
```

---

## Phase 1c — Deploy to wheelhive-vm

### Task 12: systemd service, venv, ufw, deploy

**Files:** Create `deploy/wheelhive-web.service`

**Interfaces:** Produces a running `wheelhive-web.service` on `:8080`, LAN-reachable, serving the SPA.

- [ ] **Step 1: `deploy/wheelhive-web.service`**

```ini
[Unit]
Description=WheelHive Web (companion dashboard)
After=network-online.target
Wants=network-online.target

[Service]
User=steve
WorkingDirectory=/home/steve/code/wheelhive/src
EnvironmentFile=/home/steve/code/wheelhive/.env
ExecStart=/home/steve/code/wheelhive/.web_venv/bin/python -m web.app
Restart=always
RestartSec=3
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/home/steve/code/wheelhive

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Add web secrets to the VM `.env`** (via `qm guest exec 137` as steve, or LAN SSH):

```bash
# append to /home/steve/code/wheelhive/.env (do NOT commit)
WHEELHIVE_WEB_USERNAME=sangelovich
WHEELHIVE_WEB_DB=/home/steve/code/wheelhive/trades.db
WHEELHIVE_WEB_PASSWORD=<choose a strong password>
WHEELHIVE_WEB_SECRET=<64 random hex chars>
```

- [ ] **Step 3: Deploy code + venv on the VM** (from the Mac, LAN SSH `steve@wheelhive-vm.local`)

```bash
cd /Users/steve/code/wheelhive-bot
git push origin main                     # after merging this feature branch
ssh steve@wheelhive-vm.local 'cd ~/code/wheelhive && git pull --ff-only origin main'
ssh steve@wheelhive-vm.local 'cd ~/code/wheelhive && python3 -m venv .web_venv && \
  .web_venv/bin/pip install fastapi "uvicorn[standard]" itsdangerous pandas numpy scipy yfinance pandas-ta'
```

- [ ] **Step 4: Install service + ufw rule (root via `qm guest exec 137`)**

```bash
# on Proxmox host:
qm guest exec 137 -- bash -c '
  cp /home/steve/code/wheelhive/deploy/wheelhive-web.service /etc/systemd/system/
  systemctl daemon-reload
  systemctl enable --now wheelhive-web.service
  ufw allow from 192.168.68.0/22 to any port 8080 proto tcp
  sleep 2; systemctl is-active wheelhive-web.service'
```

- [ ] **Step 5: Verify from the Mac**

```bash
curl -s http://wheelhive-vm.local:8080/health   # {"ok":true}
# browser → http://wheelhive-vm.local:8080 → login → dashboard shows (empty until data imported)
```

- [ ] **Step 6: Commit the service unit**

```bash
git add deploy/wheelhive-web.service docs/superpowers/plans/2026-07-05-wheelhive-web-companion.md
git commit -m "feat(deploy): wheelhive-web.service unit + web companion plan"
```

---

## Self-Review notes
- **Spec coverage:** Phase 0 (constants split) = Task 1. Backend (auth, accounts, positions, summary, app) = Tasks 2–8. React SPA (login + positions dashboard, AG Grid, tiles, account switcher, refresh) = Tasks 9–11. Deploy (service + ufw + venv) = Task 12. Live-price refresh = manual Refresh button (Task 11). Missing `reports/` PDFs intentionally out of scope (v1). Tax-lot/wheel-cycle out of scope (later phase).
- **Verify-during-impl flags:** exact `Db.__init__` DB-path mechanism (Task 4), `DFStats.as_dict()` keys and the `get_stock_positions` unrealized-P/L key name (Task 7). These are called out inline; confirm against source, don't guess.
- **Auth is minimal by design** (single user, LAN + session). Revisit for multi-user (per-user data isolation) when/if community login is wanted.
