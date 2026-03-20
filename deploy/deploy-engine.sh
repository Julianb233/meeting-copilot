#!/usr/bin/env bash
set -euo pipefail

# Meeting Copilot Engine -- deploy to VPS
# Usage: bash deploy/deploy-engine.sh

ENGINE_DIR="/opt/agency-workspace/meeting-copilot/engine"
SERVICE_NAME="meeting-copilot-engine"

echo "=== Deploying Meeting Copilot Engine ==="

# 1. Install/update Python deps
echo "[1/4] Installing Python dependencies..."
cd "$ENGINE_DIR"
source .venv/bin/activate
pip install -q -r requirements.txt

# 2. Install systemd service
echo "[2/4] Installing systemd service..."
sudo cp /opt/agency-workspace/meeting-copilot/deploy/meeting-copilot-engine.service \
    /etc/systemd/system/$SERVICE_NAME.service
sudo systemctl daemon-reload

# 3. Install nginx config
echo "[3/4] Installing nginx config..."
sudo cp /opt/agency-workspace/meeting-copilot/deploy/nginx/meeting-copilot.conf \
    /etc/nginx/sites-available/meeting-copilot
sudo ln -sf /etc/nginx/sites-available/meeting-copilot /etc/nginx/sites-enabled/meeting-copilot
sudo nginx -t && sudo systemctl reload nginx

# 4. Restart engine
echo "[4/4] Restarting engine..."
sudo systemctl enable $SERVICE_NAME
sudo systemctl restart $SERVICE_NAME

echo "=== Deployment complete ==="
echo "Engine status: $(systemctl is-active $SERVICE_NAME)"
echo "Health check: curl https://copilot-api.agency.dev/health"
