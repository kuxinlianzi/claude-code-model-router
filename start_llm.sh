#!/bin/bash
# start_llm.sh - Start Ollama + Model Router with health checks
# Usage: ./start_llm.sh

set -e

# ─── Configuration ─────────────────────────────────────────────────────────────

ROUTER_SCRIPT="/Users/jim/myCodes/claudeCode/model_router.py"
OLLAMA_PORT=11434
ROUTER_PORT=8888
TIMEOUT=30

# ─── Helper Functions ────────────────────────────────────────────────────────

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

check_port() {
    lsof -ti:$1 >/dev/null 2>&1
}

kill_process_on_port() {
    local port=$1
    local pid=$(lsof -ti:$port 2>/dev/null || true)
    if [ -n "$pid" ]; then
        log "Killing process on port $port (PID: $pid)..."
        kill "$pid" 2>/dev/null || true
        sleep 1
    fi
}

wait_for_service() {
    local port=$1
    local name=$2
    local timeout=${3:-$TIMEOUT}
    local count=0

    log "Waiting for $name on port $port..."
    while [ $count -lt $timeout ]; do
        if check_port $port; then
            # Port is open, try health check
            if curl -s --connect-timeout 2 http://localhost:$port >/dev/null 2>&1; then
                log "$name is ready on port $port"
                return 0
            fi
        fi
        count=$((count + 1))
        sleep 1
    done

    log "[WARN] $name may not be fully ready after ${timeout}s"
    return 1
}

check_health() {
    local port=$1
    local name=$2
    local endpoint=${3:-"/health"}

    if [ "$endpoint" = "/tags" ]; then
        endpoint="/api/tags"
    fi

    local response=$(curl -s --connect-timeout 3 http://localhost:$port$endpoint 2>/dev/null || echo "fail")

    if echo "$response" | grep -q '"name"\|"status"'; then
        echo "✅ UP"
        return 0
    else
        echo "❌ DOWN"
        return 1
    fi
}

# ─── Main ──────────────────────────────────────────────────────────────────────

echo ""
echo "========================================"
echo "  LLM Stack Starter"
echo "========================================"
echo ""

# ─── Step 1: Handle Ollama ───────────────────────────────────────────────────

log "=== Ollama Serve ==="

if check_port $OLLAMA_PORT; then
    log "Ollama already running, restarting..."
    kill_process_on_port $OLLAMA_PORT
fi

log "Starting ollama serve..."
# Redirect stdout/stderr to suppress all logs except our own
ollama serve >/dev/null 2>/tmp/ollama.log &
OLLAMA_PID=$!
sleep 2

if ! wait_for_service $OLLAMA_PORT "Ollama" 15; then
    log "ERROR: Ollama failed to start"
    log "--- Last 10 lines of ollama.log ---"
    tail -n 10 /tmp/ollama.log 2>/dev/null || true
    exit 1
fi

log "Ollama started successfully"

# ─── Step 1.5: Load Judge Model ─────────────────────────────────────────────

# Read judge model from config file if it exists
CONFIG_FILE="config.yaml"
if [ -f "$CONFIG_FILE" ]; then
    JUDGE_MODEL=$(grep -A5 "^judge:" "$CONFIG_FILE" | grep "model:" | head -1 | sed 's/.*model: *"\(.*\)"/\1/')
else
    JUDGE_MODEL="qwen3.5:2b"
fi

log "Loading judge model: $JUDGE_MODEL..."
if ! ollama list 2>/dev/null | grep -q "$JUDGE_MODEL"; then
    ollama pull "$JUDGE_MODEL"
else
    log "Model $JUDGE_MODEL already exists, skipping pull"
fi
log "Judge model loaded"

echo ""

# ─── Step 2: Start Model Router ──────────────────────────────────────────────

log "=== Model Router ==="

kill_process_on_port $ROUTER_PORT

log "Starting model router on port $ROUTER_PORT..."

# Run directly so logs go to screen
python3 $ROUTER_SCRIPT --port $ROUTER_PORT &
ROUTER_PID=$!

sleep 3

if ! check_port $ROUTER_PORT; then
    log "ERROR: Model router failed to start"
    exit 1
fi

log "Model router started (PID: $ROUTER_PID)"
echo ""

# ─── Step 3: Health Checks ───────────────────────────────────────────────────

log "=== Health Check ==="
echo ""

log "Services status:"
printf "  %-20s  %s\n" "Ollama (11434):" ""
check_health $OLLAMA_PORT "Ollama" "/tags"
printf "  %-20s  %s\n" "Router (8888):" ""
check_health $ROUTER_PORT "Router" "/health"

echo ""
log "Stack started successfully!"
echo ""

# ─── Switch settings to bklocal ──────────────────────────────────────────────
log "Switching Claude settings to bklocal..."
claude_settings.sh bklocal
if [ $? -ne 0 ]; then
    log "[WARN] Failed to switch settings, continuing anyway"
fi
echo ""

log "Endpoints:"
log "  Ollama API:  http://localhost:$OLLAMA_PORT"
log "  Router API:  http://localhost:$ROUTER_PORT/v1/messages"
echo ""
log "To stop: ./stop_llm.sh"
echo ""
