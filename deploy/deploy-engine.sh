#!/usr/bin/env bash
set -euo pipefail

# Meeting Copilot Engine -- deploy to VPS
# Usage: bash deploy/deploy-engine.sh

ENGINE_DIR="/opt/agency-workspace/meeting-copilot/engine"
SERVICE_NAME="meeting-copilot-engine"
DOMAIN="copilot-api.agency.dev"
CERT_DIR="/etc/letsencrypt/live/$DOMAIN"

echo "=== Deploying Meeting Copilot Engine ==="

# 0. Pre-flight checks
echo "[0/5] Pre-flight checks..."

# Check .env exists
if [ ! -f "$ENGINE_DIR/.env" ]; then
    echo "ERROR: $ENGINE_DIR/.env not found."
    echo "Create it from .env.example and fill in required values:"
    echo "  FIREFLIES_API_KEY, LINEAR_API_KEY, GEMINI_API_KEY,"
    echo "  PANEL_ORIGIN (Vercel URL), DEBUG=false"
    exit 1
fi
echo "  .env file found"

# Check DNS
DNS_IP=$(dig +short "$DOMAIN" 2>/dev/null || true)
if [ -z "$DNS_IP" ]; then
    echo "  WARNING: No DNS A record found for $DOMAIN"
    echo "  Add an A record pointing to this server's IP before TLS setup"
else
    echo "  DNS resolved: $DOMAIN -> $DNS_IP"
fi

# Check/obtain TLS cert
if [ -d "$CERT_DIR" ]; then
    echo "  TLS cert found at $CERT_DIR"
else
    echo "  TLS cert not found, attempting certbot..."
    if [ -n "$DNS_IP" ]; then
        sudo certbot certonly --nginx -d "$DOMAIN" \
            --non-interactive --agree-tos -m julian@aiacrobatics.com || {
            echo "  WARNING: certbot failed. TLS will not work until cert is obtained."
        }
    else
        echo "  WARNING: Skipping certbot (DNS not configured yet)"
    fi
fi

# 1. Install/update Python deps
echo "[1/5] Installing Python dependencies..."
cd "$ENGINE_DIR"
source .venv/bin/activate
pip install -q -r requirements.txt

# 2. Install systemd service
echo "[2/5] Installing systemd service..."
sudo cp /opt/agency-workspace/meeting-copilot/deploy/meeting-copilot-engine.service \
    /etc/systemd/system/$SERVICE_NAME.service
sudo systemctl daemon-reload

# 3. Install nginx config
echo "[3/5] Installing nginx config..."
sudo cp /opt/agency-workspace/meeting-copilot/deploy/nginx/meeting-copilot.conf \
    /etc/nginx/sites-available/meeting-copilot
sudo ln -sf /etc/nginx/sites-available/meeting-copilot /etc/nginx/sites-enabled/meeting-copilot
sudo nginx -t && sudo systemctl reload nginx

# 4. Restart engine
echo "[4/5] Restarting engine..."
sudo systemctl enable $SERVICE_NAME
sudo systemctl restart $SERVICE_NAME
sleep 2

# 5. Health check
echo "[5/5] Health check..."
ENGINE_STATUS=$(systemctl is-active $SERVICE_NAME 2>/dev/null || echo "unknown")
echo "  Engine service: $ENGINE_STATUS"

if curl -sf http://localhost:8901/api/health > /dev/null 2>&1; then
    echo "  Local health check: PASSED"
else
    echo "  Local health check: FAILED (engine may still be starting)"
fi

if [ -d "$CERT_DIR" ] && [ -n "$DNS_IP" ]; then
    if curl -sf "https://$DOMAIN/api/health" > /dev/null 2>&1; then
        echo "  Public health check: PASSED"
    else
        echo "  Public health check: FAILED"
    fi
else
    echo "  Public health check: SKIPPED (TLS/DNS not ready)"
fi

echo ""
echo "=== Deployment complete ==="
echo "Engine status: $ENGINE_STATUS"
echo "Health check: curl https://$DOMAIN/api/health"
