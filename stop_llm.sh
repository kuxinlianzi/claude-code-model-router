#!/bin/bash
# stop_llm.sh - Stop Ollama + Model Router stack
# Usage: ./stop_llm.sh

set -e

OLLAMA_PORT=11434
ROUTER_PORT=8888

echo ""
echo "========================================"
echo "  Stopping LLM Stack"
echo "========================================"
echo ""

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# ─── Switch settings to bkgood first ─────────────────────────────────────────

log "Switching Claude settings to bkgood..."
claude_settings.sh bkgood
if [ $? -ne 0 ]; then
    log "[WARN] Failed to switch settings, continuing anyway"
fi
echo ""

# ─── Stop Model Router ───────────────────────────────────────────────────────

kill_port() {
    local port=$1
    local name=$2
    local pid=$(lsof -ti:$port 2>/dev/null || true)

    if [ -n "$pid" ]; then
        log "Stopping $name (PID: $pid)..."
        kill "$pid" 2>/dev/null || true

        for i in $(seq 1 5); do
            if ! lsof -ti:$port >/dev/null 2>&1; then
                log "$name stopped."
                return 0
            fi
            sleep 1
        done

        log "Force killing $name..."
        kill -9 "$pid" 2>/dev/null || true
    else
        log "$name is not running."
    fi
}

kill_port $ROUTER_PORT "Model Router"

# ─── Stop Ollama ─────────────────────────────────────────────────────────────

sleep 1
kill_port $OLLAMA_PORT "Ollama"

echo ""
echo "LLM Stack stopped."
echo ""
