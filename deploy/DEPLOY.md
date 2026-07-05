# Deploying wheelhive-web to wheelhive-vm (VM 137)

Companion FastAPI dashboard, served alongside the Discord bot + MCP API. Single
user, LAN-only, session-auth. Serves the pre-built React SPA from
`src/web/static/` (no Node on the VM).

> These steps are run from the Mac. VM management uses either LAN SSH
> (`steve@wheelhive-vm.local`) or, for root, `qm guest exec 137` from the
> Proxmox host `root@192.168.68.52`.

## 0. Preconditions (verify before deploying)

- **VM Python >= 3.12.** The domain library imports `itertools.batched` (via
  `brokers/basetableprocessor.py`), which is 3.12+. Check:
  `ssh steve@wheelhive-vm.local 'python3 --version'`. If it is 3.11 or older,
  install a 3.12+ interpreter and use it to build the web venv below — the
  service will fail at import otherwise.
- The feature branch is merged to `main` and pushed (see finishing-a-branch).

## 1. Deploy code

```bash
ssh steve@wheelhive-vm.local 'cd ~/code/wheelhive && git pull --ff-only origin main'
```

## 2. Build the web venv (lean — NO discord/torch/easyocr/chromadb)

The exact dependency closure of the web app's import chain, verified on the Mac
(python3.12). Note: NOT `pandas-ta` (no distribution) and NOT `scipy` (unused on
the positions/summary path) — the plan's original draft listed those and would
fail.

```bash
ssh steve@wheelhive-vm.local 'cd ~/code/wheelhive && \
  python3.12 -m venv .web_venv && \
  .web_venv/bin/pip install --upgrade pip && \
  .web_venv/bin/pip install fastapi "uvicorn[standard]" itsdangerous httpx \
    pandas numpy yfinance markdown-pdf tabulate'
```

Smoke-test the import chain on the VM before starting the service:

```bash
ssh steve@wheelhive-vm.local 'cd ~/code/wheelhive/src && \
  ../.web_venv/bin/python -c "from web.app import create_app; create_app(); print(\"web app imports OK\")"'
```

(Also, once, confirm the bot still imports after the Phase 0 constants split —
`import bot` — since that was only ast-validated on the Mac where discord.py
isn't installed.)

## 3. Web secrets in the VM `.env` (do NOT commit)

Append to `/home/steve/code/wheelhive/.env`:

```
WHEELHIVE_WEB_USERNAME=sangelovich
WHEELHIVE_WEB_DB=/home/steve/code/wheelhive/trades.db
WHEELHIVE_WEB_PASSWORD=<choose a strong password>
WHEELHIVE_WEB_SECRET=<64 random hex chars: `openssl rand -hex 32`>
```

## 4. Install the service + open the LAN port (root, via Proxmox)

```bash
# on the Proxmox host (root@192.168.68.52):
qm guest exec 137 -- bash -c '
  cp /home/steve/code/wheelhive/deploy/wheelhive-web.service /etc/systemd/system/
  systemctl daemon-reload
  systemctl enable --now wheelhive-web.service
  ufw allow from 192.168.68.0/22 to any port 8080 proto tcp
  sleep 2; systemctl is-active wheelhive-web.service'
```

## 5. Verify from the Mac

```bash
curl -s http://wheelhive-vm.local:8080/health          # {"ok":true}
# browser -> http://wheelhive-vm.local:8080 -> login -> dashboard
# (grids empty until data is imported; tiles show 0 / current year)
```

## Known watch-items

- **systemd hardening vs yfinance cache.** `ProtectHome=read-only` +
  `ReadWritePaths=/home/steve/code/wheelhive` lets the service write `trades.db`
  (WAL) but makes the rest of `$HOME` read-only. If live-quote refresh (yfinance)
  needs to write a cache under `$HOME/.cache`, it will be blocked. Not triggered
  with an empty DB (no positions -> no quote fetches). If quote refresh errors
  once data exists, add a writable cache dir to `ReadWritePaths` (or set an env
  pointing yfinance's cache into `~/code/wheelhive`).
- **Port 8000 (MCP API)** was Tailscale-only; unrelated to this service (:8080).
