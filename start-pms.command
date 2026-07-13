#!/bin/zsh
set -u

ROOT_DIR="${0:A:h}"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
RUNTIME_DIR="$ROOT_DIR/.runtime"
LOG_DIR="$RUNTIME_DIR/logs"
PID_DIR="$RUNTIME_DIR/pids"

BACKEND_PORT=8000
FRONTEND_PORT=5174
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"
BACKEND_DEPS="$BACKEND_DIR/.venv-deps312"
SQLITE_DB_PATH="$ROOT_DIR/backend/data/pms-dev.db"
DB_DIALECT=sqlite

mkdir -p "$LOG_DIR" "$PID_DIR" "$BACKEND_DIR/data"

timestamp() {
  date "+%Y-%m-%d %H:%M:%S"
}

log() {
  printf "[%s] %s\n" "$(timestamp)" "$1"
}

port_pid() {
  lsof -tiTCP:"$1" -sTCP:LISTEN 2>/dev/null | head -1
}

stop_port() {
  local port="$1"
  local label="$2"
  local pids
  pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -z "$pids" ]]; then
    return 0
  fi
  local pid_list
  pid_list="$(printf "%s\n" "$pids" | tr '\n' ' ')"
  log "Stopping $label listener(s) on port $port: $pid_list"
  for pid in ${(f)pids}; do
    kill "$pid" 2>/dev/null || true
  done
  local attempts=0
  while [[ -n "$(port_pid "$port")" ]] && (( attempts < 20 )); do
    sleep 0.1
    (( attempts++ ))
  done

  local remaining
  remaining="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "$remaining" ]]; then
    log "$label did not stop gracefully; forcing the remaining listener(s) to exit."
    for pid in ${(f)remaining}; do
      kill -9 "$pid" 2>/dev/null || true
    done
    sleep 0.2
  fi

  if [[ -n "$(port_pid "$port")" ]]; then
    log "Unable to stop $label on port $port."
    return 1
  fi
}

wait_for_url() {
  local url="$1"
  local name="$2"
  local tries=40
  local i=1
  while (( i <= tries )); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      log "$name is ready: $url"
      return 0
    fi
    sleep 0.25
    (( i++ ))
  done
  log "$name did not become ready in time: $url"
  return 1
}

choose_python() {
  local bundled="/Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
  if [[ -x "$bundled" ]]; then
    printf "%s" "$bundled"
    return 0
  fi
  if command -v python3.12 >/dev/null 2>&1; then
    command -v python3.12
    return 0
  fi
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return 0
  fi
  return 1
}

PYTHON_BIN="$(choose_python || true)"
if [[ -z "$PYTHON_BIN" ]]; then
  log "Python was not found. Please install Python 3.12."
  exit 1
fi

PYTHON_VERSION="$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)"
if [[ "$PYTHON_VERSION" != "3.12" ]]; then
  log "Backend dependencies require Python 3.12, but $PYTHON_BIN is Python $PYTHON_VERSION."
  log "Install Python 3.12 or run from Codex where the bundled Python is available."
  exit 1
fi

if [[ ! -d "$BACKEND_DEPS" ]]; then
  log "Backend dependency directory is missing: $BACKEND_DEPS"
  log "Install backend dependencies for Python 3.12 first."
  exit 1
fi

if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  log "Frontend dependencies are missing. Run npm install in $FRONTEND_DIR first."
  exit 1
fi

stop_pid_file() {
  local pid_file="$1"
  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      sleep 0.5
    fi
    rm -f "$pid_file"
  fi
}

if [[ "${PMS_FORCE_RESTART:-0}" == "1" ]]; then
  log "Force restart requested."
  stop_pid_file "$PID_DIR/backend.pid"
  stop_pid_file "$PID_DIR/frontend.pid"
  stop_port "$BACKEND_PORT" "backend" || exit 1
  stop_port "$FRONTEND_PORT" "frontend" || exit 1
fi

start_backend() {
  local existing
  existing="$(port_pid "$BACKEND_PORT")"
  if [[ -n "$existing" ]]; then
    log "Backend port $BACKEND_PORT is already listening, leaving PID $existing running."
    return 0
  fi

  log "Starting backend on http://127.0.0.1:$BACKEND_PORT"
  (
    cd "$BACKEND_DIR" || exit 1
    nohup env \
      PYTHONPATH="$BACKEND_DEPS${PYTHONPATH:+:$PYTHONPATH}" \
      DB_DIALECT=sqlite \
      SQLITE_DB_PATH="$SQLITE_DB_PATH" \
      "$PYTHON_BIN" -m uvicorn main:app --host 127.0.0.1 --port "$BACKEND_PORT" \
      </dev/null >> "$BACKEND_LOG" 2>&1 &
    echo $! > "$PID_DIR/backend.pid"
  )
}

start_frontend() {
  local existing
  existing="$(port_pid "$FRONTEND_PORT")"
  if [[ -n "$existing" ]]; then
    log "Frontend port $FRONTEND_PORT is already listening, leaving PID $existing running."
    return 0
  fi

  log "Starting frontend on http://127.0.0.1:$FRONTEND_PORT"
  (
    cd "$FRONTEND_DIR" || exit 1
    nohup npm run dev -- --host 127.0.0.1 --port "$FRONTEND_PORT" --strictPort \
      </dev/null >> "$FRONTEND_LOG" 2>&1 &
    echo $! > "$PID_DIR/frontend.pid"
  )
}

check_admin_login() {
  local body
  body="$(curl -fsS -X POST "http://127.0.0.1:$FRONTEND_PORT/api/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"username":"admin","password":"admin123","remember_me":false}' 2>/dev/null || true)"
  if [[ "$body" == *"access_token"* ]]; then
    log "Admin login API is ready: admin / admin123"
    return 0
  fi
  log "Admin login API is not ready. Backend log: $BACKEND_LOG"
  return 1
}

start_backend
start_frontend

wait_for_url "http://127.0.0.1:$BACKEND_PORT/docs" "Backend"
wait_for_url "http://127.0.0.1:$FRONTEND_PORT/" "Frontend"
if ! check_admin_login; then
  log "Restarting frontend because the Vite API proxy is not healthy."
  stop_port "$FRONTEND_PORT" "frontend"
  start_frontend
  wait_for_url "http://127.0.0.1:$FRONTEND_PORT/" "Frontend"
  check_admin_login
fi

log "PMS is available at http://127.0.0.1:$FRONTEND_PORT"
log "Logs:"
log "  Backend:  $BACKEND_LOG"
log "  Frontend: $FRONTEND_LOG"

if [[ "${PMS_NO_PAUSE:-0}" != "1" && -t 0 ]]; then
  printf "\nPress Enter to close this window..."
  read -r
fi
