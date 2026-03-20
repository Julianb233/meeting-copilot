---
phase: 1-project-scaffold-infrastructure
plan: 03
type: execute
wave: 2
depends_on: ["1-01", "1-02"]
files_modified:
  - deploy/nginx/meeting-copilot.conf
  - deploy/systemd/meeting-copilot-engine.service
  - deploy/scripts/deploy-engine.sh
  - deploy/scripts/deploy-panel.sh
  - .env.example
  - .gitignore
  - engine/.env.example
  - panel/.env.example
autonomous: true

must_haves:
  truths:
    - "Nginx config proxies /ws to WebSocket and /api to REST with correct headers"
    - "Systemd service file can manage the engine process lifecycle"
    - "Deploy scripts exist for both panel (Vercel) and engine (VPS)"
    - "Environment variable templates document all required config"
    - "Gitignore excludes venv, node_modules, .env, dist, __pycache__"
  artifacts:
    - path: "deploy/nginx/meeting-copilot.conf"
      provides: "Nginx reverse proxy config with TLS and WebSocket upgrade"
      contains: "proxy_set_header Upgrade"
    - path: "deploy/systemd/meeting-copilot-engine.service"
      provides: "Systemd unit file for engine process management"
      contains: "uvicorn"
    - path: "deploy/scripts/deploy-engine.sh"
      provides: "Engine deployment script for VPS"
      contains: "pip install"
    - path: ".env.example"
      provides: "Root environment variable template"
      contains: "FIREFLIES_API_KEY"
    - path: ".gitignore"
      provides: "Git ignore rules for both panel and engine"
      contains: "node_modules"
  key_links:
    - from: "deploy/nginx/meeting-copilot.conf"
      to: "engine/src/main.py"
      via: "Port proxy (8901 for REST, /ws for WebSocket)"
      pattern: "proxy_pass.*8901"
    - from: "deploy/systemd/meeting-copilot-engine.service"
      to: "engine/src/main.py"
      via: "ExecStart uvicorn command"
      pattern: "src.main:app"
---

<objective>
Create deployment infrastructure: nginx reverse proxy config for WebSocket TLS, systemd service file for the engine, deployment scripts, environment variable templates, and project-wide gitignore.

Purpose: Provide everything needed to deploy the panel to Vercel and the engine to the VPS with TLS-terminated WebSocket support through nginx.

Output: Deployment configs, scripts, and env templates ready for use.
</objective>

<execution_context>
@~/.claude/get-shit-done/workflows/execute-plan.md
@~/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/research/STACK.md
@.planning/research/ARCHITECTURE.md
@.planning/phases/1-project-scaffold-infrastructure/1-01-SUMMARY.md
@.planning/phases/1-project-scaffold-infrastructure/1-02-SUMMARY.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Nginx config and systemd service for VPS deployment</name>
  <files>
    deploy/nginx/meeting-copilot.conf
    deploy/systemd/meeting-copilot-engine.service
  </files>
  <action>
    1. Create `deploy/nginx/meeting-copilot.conf` — nginx reverse proxy config following STACK.md and ARCHITECTURE.md patterns. This is a config FILE to be symlinked into `/etc/nginx/sites-available/` on the VPS. Use placeholder domain `copilot-api.aiacrobatics.com` (user will confirm actual domain):

       ```nginx
       # Meeting Copilot Engine — nginx reverse proxy
       # Symlink to /etc/nginx/sites-available/meeting-copilot
       # sudo ln -s /opt/agency-workspace/meeting-copilot/deploy/nginx/meeting-copilot.conf /etc/nginx/sites-available/meeting-copilot

       server {
           listen 443 ssl;
           server_name copilot-api.aiacrobatics.com;

           ssl_certificate /etc/letsencrypt/live/copilot-api.aiacrobatics.com/fullchain.pem;
           ssl_certificate_key /etc/letsencrypt/live/copilot-api.aiacrobatics.com/privkey.pem;

           # WebSocket endpoint — proxied to FastAPI
           location /ws {
               proxy_pass http://127.0.0.1:8901;
               proxy_http_version 1.1;
               proxy_set_header Upgrade $http_upgrade;
               proxy_set_header Connection "upgrade";
               proxy_set_header Host $host;
               proxy_set_header X-Real-IP $remote_addr;
               proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
               proxy_set_header X-Forwarded-Proto $scheme;
               proxy_read_timeout 86400;   # 24h keepalive for long meetings
               proxy_send_timeout 86400;
           }

           # REST API — proxied to same FastAPI process
           location /api {
               proxy_pass http://127.0.0.1:8901;
               proxy_set_header Host $host;
               proxy_set_header X-Real-IP $remote_addr;
               proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
               proxy_set_header X-Forwarded-Proto $scheme;
           }

           # CORS headers for Zoom iframe
           # Panel origin will be the Vercel deployment URL
           add_header Access-Control-Allow-Origin "https://meeting-copilot.vercel.app" always;
           add_header Access-Control-Allow-Methods "GET, POST, OPTIONS" always;
           add_header Access-Control-Allow-Headers "Authorization, Content-Type" always;

           # CSP for Zoom compatibility
           add_header Content-Security-Policy "default-src 'self'; connect-src 'self' wss://copilot-api.aiacrobatics.com *.zoom.us; script-src 'self' *.zoom.us 'unsafe-eval'; frame-ancestors *.zoom.us;" always;
       }

       # HTTP -> HTTPS redirect
       server {
           listen 80;
           server_name copilot-api.aiacrobatics.com;
           return 301 https://$host$request_uri;
       }
       ```

       NOTE: Both /ws and /api proxy to the same port 8901 because FastAPI serves both from one process (as per STACK.md architecture decision). The original roadmap mentioned port 8900 for WS and 8901 for REST, but the research concluded single-port with path routing is better.

    2. Create `deploy/systemd/meeting-copilot-engine.service`:
       ```ini
       [Unit]
       Description=Meeting Copilot Engine (FastAPI + WebSocket)
       After=network.target

       [Service]
       Type=simple
       User=agent4
       Group=agency
       WorkingDirectory=/opt/agency-workspace/meeting-copilot/engine
       Environment=PATH=/opt/agency-workspace/meeting-copilot/engine/.venv/bin:/usr/local/bin:/usr/bin
       EnvironmentFile=/opt/agency-workspace/meeting-copilot/.env
       ExecStart=/opt/agency-workspace/meeting-copilot/engine/.venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8901 --workers 1
       Restart=always
       RestartSec=5
       StandardOutput=journal
       StandardError=journal

       [Install]
       WantedBy=multi-user.target
       ```

       NOTE: `--workers 1` is intentional — WebSocket state is in-process, multiple workers would break connection state sharing.
  </action>
  <verify>
    - `nginx -t -c /dev/stdin < deploy/nginx/meeting-copilot.conf` or manually verify the config has correct syntax (nginx -t requires the full config context, so just verify the file exists and contains key directives)
    - `grep "proxy_set_header Upgrade" deploy/nginx/meeting-copilot.conf` returns a match
    - `grep "proxy_pass.*8901" deploy/nginx/meeting-copilot.conf` returns matches for both /ws and /api
    - `grep "uvicorn" deploy/systemd/meeting-copilot-engine.service` returns the ExecStart line
    - `grep "workers 1" deploy/systemd/meeting-copilot-engine.service` confirms single worker
  </verify>
  <done>Nginx config handles TLS termination, WebSocket upgrade headers, and CORS for Zoom iframe. Systemd service manages the engine process with auto-restart.</done>
</task>

<task type="auto">
  <name>Task 2: Deploy scripts, env templates, and gitignore</name>
  <files>
    deploy/scripts/deploy-engine.sh
    deploy/scripts/deploy-panel.sh
    .env.example
    engine/.env.example
    panel/.env.example
    .gitignore
  </files>
  <action>
    1. Create `deploy/scripts/deploy-engine.sh`:
       ```bash
       #!/usr/bin/env bash
       set -euo pipefail

       # Deploy Meeting Copilot Engine to VPS
       # Run from project root: ./deploy/scripts/deploy-engine.sh

       ENGINE_DIR="/opt/agency-workspace/meeting-copilot/engine"
       SERVICE_NAME="meeting-copilot-engine"

       echo "==> Pulling latest code..."
       cd /opt/agency-workspace/meeting-copilot
       git pull origin main

       echo "==> Installing Python dependencies..."
       cd "$ENGINE_DIR"
       source .venv/bin/activate
       pip install -r requirements.txt --quiet

       echo "==> Running tests..."
       python -m pytest tests/ -v

       echo "==> Restarting service..."
       sudo systemctl restart "$SERVICE_NAME"
       sudo systemctl status "$SERVICE_NAME" --no-pager

       echo "==> Deploy complete. Check: curl https://copilot-api.aiacrobatics.com/api/health"
       ```

    2. Create `deploy/scripts/deploy-panel.sh`:
       ```bash
       #!/usr/bin/env bash
       set -euo pipefail

       # Deploy Meeting Copilot Panel to Vercel
       # Run from project root: ./deploy/scripts/deploy-panel.sh

       PANEL_DIR="/opt/agency-workspace/meeting-copilot/panel"

       echo "==> Building panel..."
       cd "$PANEL_DIR"
       npm run build

       echo "==> Deploying to Vercel..."
       cd "$PANEL_DIR"
       npx vercel --prod --yes

       echo "==> Deploy complete."
       ```

    3. Create `.env.example` (root-level, used by systemd EnvironmentFile):
       ```bash
       # Meeting Copilot — Environment Variables
       # Copy to .env and fill in values

       # Engine
       ENGINE_HOST=0.0.0.0
       ENGINE_PORT=8901
       DEBUG=false

       # Panel origin for CORS
       PANEL_ORIGIN=https://meeting-copilot.vercel.app

       # AI / Classification (LiteLLM)
       GEMINI_API_KEY=
       OPENAI_API_KEY=
       ANTHROPIC_API_KEY=

       # External Services
       FIREFLIES_API_KEY=
       LINEAR_API_KEY=

       # Google APIs (OAuth2 — service account or user credentials)
       GOOGLE_APPLICATION_CREDENTIALS=

       # Zoom App (set during Phase 4)
       ZOOM_CLIENT_ID=
       ZOOM_CLIENT_SECRET=
       ZOOM_REDIRECT_URI=
       ```

    4. Create `engine/.env.example`:
       ```bash
       # Engine-specific env (for local development)
       # Copy to engine/.env

       ENGINE_HOST=0.0.0.0
       ENGINE_PORT=8901
       DEBUG=true
       PANEL_ORIGIN=http://localhost:3000
       ```

    5. Create `panel/.env.example`:
       ```bash
       # Panel-specific env (for local development)
       # Copy to panel/.env

       VITE_WS_URL=ws://localhost:8901/ws
       VITE_API_URL=http://localhost:8901/api
       ```

    6. Update `.gitignore` (replace existing if present — the current one at project root):
       ```gitignore
       # Dependencies
       node_modules/
       .venv/

       # Build outputs
       dist/
       build/
       *.egg-info/

       # Environment
       .env
       .env.local
       .env.*.local

       # Python
       __pycache__/
       *.py[cod]
       *.pyo
       .mypy_cache/
       .ruff_cache/
       .pytest_cache/

       # IDE
       .vscode/
       .idea/
       *.swp
       *.swo

       # OS
       .DS_Store
       Thumbs.db

       # Vercel
       .vercel/

       # Logs
       *.log
       ```

    7. Make deploy scripts executable:
       ```bash
       chmod +x deploy/scripts/deploy-engine.sh deploy/scripts/deploy-panel.sh
       ```
  </action>
  <verify>
    - `ls deploy/scripts/deploy-engine.sh deploy/scripts/deploy-panel.sh` both exist
    - `test -x deploy/scripts/deploy-engine.sh && echo "executable"` prints "executable"
    - `test -x deploy/scripts/deploy-panel.sh && echo "executable"` prints "executable"
    - `ls .env.example engine/.env.example panel/.env.example` all exist
    - `grep "node_modules" .gitignore` returns a match
    - `grep "__pycache__" .gitignore` returns a match
    - `grep ".env" .gitignore` returns a match
    - `grep "FIREFLIES_API_KEY" .env.example` returns a match
  </verify>
  <done>Deploy scripts for both engine (VPS/systemd) and panel (Vercel) are executable. Environment variable templates document all required config. Gitignore covers both Python and Node.js artifacts.</done>
</task>

</tasks>

<verification>
- All deployment files exist in `deploy/` directory
- Nginx config contains WebSocket upgrade headers and CORS for Zoom
- Systemd service targets the correct working directory and uvicorn command
- Deploy scripts are executable
- Env templates list all required variables
- Gitignore covers node_modules, .venv, .env, __pycache__, dist
</verification>

<success_criteria>
Deployment infrastructure complete with:
1. Nginx reverse proxy config with TLS, WebSocket upgrade, CORS for Zoom iframe
2. Systemd service file for engine process management
3. Deploy script for engine (git pull, pip install, test, restart)
4. Deploy script for panel (build, vercel deploy)
5. Environment variable templates for root, engine, and panel
6. Comprehensive gitignore for both Python and Node.js
</success_criteria>

<output>
After completion, create `.planning/phases/1-project-scaffold-infrastructure/1-03-SUMMARY.md`
</output>
