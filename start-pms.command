#!/bin/zsh
set -u

LAUNCHER_ROOT="${0:A:h}"
RUNTIME_DIR="${PMS_RUNTIME_DIR:-$LAUNCHER_ROOT/.runtime}"
LOG_DIR="$RUNTIME_DIR/logs"
PID_DIR="$RUNTIME_DIR/pids"
DATA_DIR="$RUNTIME_DIR/data"
ACTIVE_SOURCE_FILE="$RUNTIME_DIR/active-source"
SOURCE_STATE_FILE="$RUNTIME_DIR/active-source.state"
START_LOCK_DIR="$RUNTIME_DIR/start.lock"
START_LOCK_OWNER="$START_LOCK_DIR/pid"
BACKEND_SPAWN_FILE="$PID_DIR/backend.spawn.$$"
FRONTEND_SPAWN_FILE="$PID_DIR/frontend.spawn.$$"
BACKEND_VERSION_FILE="$PID_DIR/backend.version"
FRONTEND_VERSION_FILE="$PID_DIR/frontend.version"

BACKEND_PORT="${PMS_BACKEND_PORT:-8000}"
FRONTEND_PORT="${PMS_FRONTEND_PORT:-5174}"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"
SQLITE_DB_PATH="${PMS_SQLITE_DB_PATH:-$RUNTIME_DIR/data/pms-dev.db}"

mkdir -p "$LOG_DIR" "$PID_DIR" "$DATA_DIR"

timestamp() {
  date "+%Y-%m-%d %H:%M:%S"
}

log() {
  printf "[%s] %s\n" "$(timestamp)" "$1"
}

validate_source_dir() {
  local source_dir="$1"
  [[ -f "$source_dir/backend/main.py" && -f "$source_dir/frontend/package.json" ]]
}

resolve_source_dir() {
  local requested=""
  local resolved=""

  if [[ -n "${PMS_SOURCE_DIR:-}" ]]; then
    requested="$PMS_SOURCE_DIR"
  elif [[ -f "$ACTIVE_SOURCE_FILE" ]]; then
    IFS= read -r requested < "$ACTIVE_SOURCE_FILE" || true
  elif [[ -f "$SOURCE_STATE_FILE" ]]; then
    printf "The PMS active source configuration is missing: %s\n" "$ACTIVE_SOURCE_FILE" >&2
    printf "Restore the configured source path instead of falling back to another version.\n" >&2
    return 1
  else
    requested="$LAUNCHER_ROOT"
  fi

  if [[ -z "$requested" ]]; then
    printf "The PMS active source configuration is empty: %s\n" "$ACTIVE_SOURCE_FILE" >&2
    return 1
  fi

  resolved="$(cd "$requested" 2>/dev/null && pwd -P)" || {
    printf "The configured PMS source directory does not exist: %s\n" "$requested" >&2
    printf "Update %s to an existing PMS source directory.\n" "$ACTIVE_SOURCE_FILE" >&2
    return 1
  }

  if ! validate_source_dir "$resolved"; then
    printf "The configured directory is not a complete PMS source tree: %s\n" "$resolved" >&2
    return 1
  fi

  printf "%s" "$resolved"
}

SOURCE_DIR="$(resolve_source_dir)" || exit 1
BACKEND_DIR="$SOURCE_DIR/backend"
FRONTEND_DIR="$SOURCE_DIR/frontend"
BACKEND_DEPS="${PMS_BACKEND_DEPS:-$BACKEND_DIR/.venv-deps312}"

if [[ "$SQLITE_DB_PATH" != /* ]]; then
  SQLITE_DB_PATH="$LAUNCHER_ROOT/$SQLITE_DB_PATH"
fi

SOURCE_BRANCH="$(git -C "$SOURCE_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || printf "unversioned")"
SOURCE_COMMIT="$(git -C "$SOURCE_DIR" rev-parse --short HEAD 2>/dev/null || printf "unknown")"

persist_source_state() {
  if [[ -f "$ACTIVE_SOURCE_FILE" ]]; then
    printf "initialized\n" > "$SOURCE_STATE_FILE" || return 1
    return 0
  fi

  if [[ -z "${PMS_SOURCE_DIR:-}" ]]; then
    printf "%s\n" "$SOURCE_DIR" > "$ACTIVE_SOURCE_FILE" || return 1
    printf "initialized\n" > "$SOURCE_STATE_FILE" || return 1
    log "Initialized active source configuration: $SOURCE_DIR"
  fi
}

port_pid() {
  lsof -tiTCP:"$1" -sTCP:LISTEN 2>/dev/null | head -1
}

process_cwd() {
  local pid="$1"
  lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -1
}

pid_file_value() {
  local pid_file="$1"
  if [[ -f "$pid_file" ]]; then
    tr -d '[:space:]' < "$pid_file"
  fi
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
  while [[ -n "$(port_pid "$port")" ]] && (( attempts < 30 )); do
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

cleanup_failed_start() {
  local label="$1"
  local port="$2"
  local spawn_file="$3"
  local pid_file="$4"
  local spawn_pid=""
  local version_file="${pid_file%.pid}.version"

  if [[ -f "$spawn_file" ]]; then
    spawn_pid="$(pid_file_value "$spawn_file")"
    if [[ -n "$spawn_pid" ]] && kill -0 "$spawn_pid" 2>/dev/null; then
      kill "$spawn_pid" 2>/dev/null || true
      sleep 0.2
    fi
  fi

  stop_port "$port" "$label" || true
  rm -f "$spawn_file" "$pid_file" "$version_file"
}

cleanup_pending_starts() {
  if [[ -f "$BACKEND_SPAWN_FILE" ]]; then
    cleanup_failed_start "backend" "$BACKEND_PORT" "$BACKEND_SPAWN_FILE" "$PID_DIR/backend.pid"
  fi
  if [[ -f "$FRONTEND_SPAWN_FILE" ]]; then
    cleanup_failed_start "frontend" "$FRONTEND_PORT" "$FRONTEND_SPAWN_FILE" "$PID_DIR/frontend.pid"
  fi
}

release_start_lock() {
  local owner=""
  if [[ -f "$START_LOCK_OWNER" ]]; then
    owner="$(pid_file_value "$START_LOCK_OWNER")"
  fi
  if [[ "$owner" == "$$" ]]; then
    rm -f "$START_LOCK_OWNER"
    rmdir "$START_LOCK_DIR" 2>/dev/null || true
  fi
}

launcher_exit_handler() {
  cleanup_pending_starts
  release_start_lock
}

acquire_start_lock() {
  local attempts=0
  local owner=""
  local announced=0

  while ! mkdir "$START_LOCK_DIR" 2>/dev/null; do
    owner=""
    if [[ -f "$START_LOCK_OWNER" ]]; then
      owner="$(pid_file_value "$START_LOCK_OWNER")"
    fi

    if [[ -z "$owner" ]]; then
      local lock_mtime=""
      local now=""
      lock_mtime="$(stat -f %m "$START_LOCK_DIR" 2>/dev/null || true)"
      now="$(date +%s)"
      if [[ -n "$lock_mtime" ]] && (( now - lock_mtime >= 2 )); then
        rm -f "$START_LOCK_OWNER"
        rmdir "$START_LOCK_DIR" 2>/dev/null || true
        continue
      fi
    fi

    if [[ -n "$owner" ]] && ! kill -0 "$owner" 2>/dev/null; then
      rm -f "$START_LOCK_OWNER"
      rmdir "$START_LOCK_DIR" 2>/dev/null || true
      continue
    fi

    if (( announced == 0 )); then
      log "Another PMS launcher is running; waiting for it to finish."
      announced=1
    fi
    sleep 0.25
    (( attempts++ ))
    if (( attempts >= 120 )); then
      log "Timed out waiting for the PMS launcher lock: $START_LOCK_DIR"
      return 1
    fi
  done

  printf "%s\n" "$$" > "$START_LOCK_OWNER" || {
    rmdir "$START_LOCK_DIR" 2>/dev/null || true
    return 1
  }
  trap launcher_exit_handler EXIT
  trap 'exit 130' HUP INT TERM
}

listener_matches_source() {
  local port="$1"
  local expected_cwd="$2"
  local pid_file="$3"
  local version_file="${pid_file%.pid}.version"
  local pid
  pid="$(port_pid "$port")"
  [[ -n "$pid" ]] || return 1
  [[ "$(process_cwd "$pid")" == "$expected_cwd" ]] || return 1
  [[ "$(pid_file_value "$pid_file")" == "$pid" ]] || return 1
  [[ "$(pid_file_value "$version_file")" == "$SOURCE_COMMIT" ]] || return 1
}

ensure_listener_source() {
  local port="$1"
  local label="$2"
  local expected_cwd="$3"
  local pid_file="$4"
  local version_file="${pid_file%.pid}.version"
  local existing
  existing="$(port_pid "$port")"

  if [[ -z "$existing" ]]; then
    rm -f "$pid_file" "$version_file"
    return 1
  fi

  if listener_matches_source "$port" "$expected_cwd" "$pid_file"; then
    log "Reusing managed $label PID $existing from $expected_cwd."
    return 0
  fi

  local actual_cwd
  local recorded_pid
  local recorded_version
  actual_cwd="$(process_cwd "$existing")"
  recorded_pid="$(pid_file_value "$pid_file")"
  recorded_version="$(pid_file_value "$version_file")"
  log "$label port $port is occupied by an unmanaged or mismatched process."
  log "  Expected source: $expected_cwd"
  log "  Actual source:   ${actual_cwd:-unknown}"
  log "  Listener PID:    $existing; recorded PID: ${recorded_pid:-none}"
  log "  Expected commit: $SOURCE_COMMIT; recorded commit: ${recorded_version:-none}"
  stop_port "$port" "$label" || return 2
  rm -f "$pid_file" "$version_file"
  return 1
}

record_listener_pid() {
  local port="$1"
  local pid_file="$2"
  local label="$3"
  local version_file="${pid_file%.pid}.version"
  local pid
  pid="$(port_pid "$port")"
  if [[ -z "$pid" ]]; then
    log "Cannot record $label PID because port $port is not listening."
    return 1
  fi
  printf "%s\n" "$pid" > "$pid_file" || return 1
  printf "%s\n" "$SOURCE_COMMIT" > "$version_file" || return 1
}

finalize_listener_start() {
  local label="$1"
  local port="$2"
  local expected_cwd="$3"
  local spawn_file="$4"
  local pid_file="$5"

  if ! record_listener_pid "$port" "$pid_file" "$label"; then
    cleanup_failed_start "$label" "$port" "$spawn_file" "$pid_file"
    return 1
  fi
  if ! listener_matches_source "$port" "$expected_cwd" "$pid_file"; then
    log "$label source verification failed after startup."
    cleanup_failed_start "$label" "$port" "$spawn_file" "$pid_file"
    return 1
  fi
  rm -f "$spawn_file"
}

print_source_summary() {
  log "Launcher: $LAUNCHER_ROOT/start-pms.command"
  log "Source:   $SOURCE_DIR"
  log "Branch:   $SOURCE_BRANCH"
  log "Commit:   $SOURCE_COMMIT"
  log "Database: $SQLITE_DB_PATH"
}

print_listener_status() {
  local port="$1"
  local label="$2"
  local expected_cwd="$3"
  local pid_file="$4"
  local pid
  pid="$(port_pid "$port")"
  if [[ -z "$pid" ]]; then
    log "$label: stopped (port $port)"
    return 0
  fi

  local cwd
  local ownership="mismatched or unmanaged"
  cwd="$(process_cwd "$pid")"
  if listener_matches_source "$port" "$expected_cwd" "$pid_file"; then
    ownership="managed and current"
  fi
  log "$label: PID $pid, port $port, $ownership"
  log "  Process source: ${cwd:-unknown}"
}

print_source_summary

if [[ "${PMS_STATUS_ONLY:-0}" == "1" ]]; then
  print_listener_status "$BACKEND_PORT" "Backend" "$BACKEND_DIR" "$PID_DIR/backend.pid"
  print_listener_status "$FRONTEND_PORT" "Frontend" "$FRONTEND_DIR" "$PID_DIR/frontend.pid"
  exit 0
fi

initialize_database() {
  if [[ -f "$SQLITE_DB_PATH" ]]; then
    return 0
  fi

  mkdir -p "${SQLITE_DB_PATH:h}"
  local seed=""
  if [[ -f "$SOURCE_DIR/backend/data/pms-dev.db" ]]; then
    seed="$SOURCE_DIR/backend/data/pms-dev.db"
  elif [[ -f "$LAUNCHER_ROOT/backend/data/pms-dev.db" ]]; then
    seed="$LAUNCHER_ROOT/backend/data/pms-dev.db"
  fi

  if [[ -n "$seed" ]]; then
    local seed_target="${SQLITE_DB_PATH}.bootstrap.$$"
    rm -f "$seed_target"
    "$PYTHON_BIN" -c 'import sqlite3, sys
source = sqlite3.connect(sys.argv[1])
target = sqlite3.connect(sys.argv[2])
try:
    source.backup(target)
finally:
    target.close()
    source.close()' "$seed" "$seed_target" || {
      rm -f "$seed_target"
      return 1
    }
    mv -f "$seed_target" "$SQLITE_DB_PATH" || {
      rm -f "$seed_target"
      return 1
    }
    log "Initialized stable local database from $seed"
  else
    log "No existing local database was found; backend will create $SQLITE_DB_PATH"
  fi
}

wait_for_url() {
  local url="$1"
  local name="$2"
  local tries=60
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

acquire_start_lock || exit 1
persist_source_state || {
  log "Failed to persist the active PMS source configuration."
  exit 1
}

initialize_database || {
  log "Failed to initialize the stable local database."
  exit 1
}

if [[ "${PMS_FORCE_RESTART:-0}" == "1" ]]; then
  log "Force restart requested."
  stop_port "$BACKEND_PORT" "backend" || exit 1
  stop_port "$FRONTEND_PORT" "frontend" || exit 1
  rm -f "$PID_DIR/backend.pid" "$PID_DIR/frontend.pid" "$BACKEND_VERSION_FILE" "$FRONTEND_VERSION_FILE"
fi

start_backend() {
  if ensure_listener_source "$BACKEND_PORT" "backend" "$BACKEND_DIR" "$PID_DIR/backend.pid"; then
    return 0
  else
    local result=$?
    (( result == 1 )) || return "$result"
  fi

  log "Starting backend on http://127.0.0.1:$BACKEND_PORT"
  rm -f "$BACKEND_SPAWN_FILE"
  (
    cd "$BACKEND_DIR" || exit 1
    nohup env \
      PYTHONPATH="$BACKEND_DEPS${PYTHONPATH:+:$PYTHONPATH}" \
      DB_DIALECT=sqlite \
      SQLITE_DB_PATH="$SQLITE_DB_PATH" \
      PMS_SOURCE_DIR="$SOURCE_DIR" \
      PMS_SOURCE_COMMIT="$SOURCE_COMMIT" \
      "$PYTHON_BIN" -m uvicorn main:app --host 127.0.0.1 --port "$BACKEND_PORT" \
      </dev/null >> "$BACKEND_LOG" 2>&1 &
    printf "%s\n" "$!" > "$BACKEND_SPAWN_FILE"
  )
}

start_frontend() {
  if ensure_listener_source "$FRONTEND_PORT" "frontend" "$FRONTEND_DIR" "$PID_DIR/frontend.pid"; then
    return 0
  else
    local result=$?
    (( result == 1 )) || return "$result"
  fi

  log "Starting frontend on http://127.0.0.1:$FRONTEND_PORT"
  rm -f "$FRONTEND_SPAWN_FILE"
  (
    cd "$FRONTEND_DIR" || exit 1
    nohup env \
      VITE_PMS_SOURCE_COMMIT="$SOURCE_COMMIT" \
      npm run dev -- --host 127.0.0.1 --port "$FRONTEND_PORT" --strictPort \
      </dev/null >> "$FRONTEND_LOG" 2>&1 &
    printf "%s\n" "$!" > "$FRONTEND_SPAWN_FILE"
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

start_backend || exit 1
if ! wait_for_url "http://127.0.0.1:$BACKEND_PORT/docs" "Backend"; then
  log "Backend startup failed. Check: $BACKEND_LOG"
  cleanup_failed_start "backend" "$BACKEND_PORT" "$BACKEND_SPAWN_FILE" "$PID_DIR/backend.pid"
  exit 1
fi
finalize_listener_start "backend" "$BACKEND_PORT" "$BACKEND_DIR" "$BACKEND_SPAWN_FILE" "$PID_DIR/backend.pid" || exit 1

start_frontend || exit 1
if ! wait_for_url "http://127.0.0.1:$FRONTEND_PORT/" "Frontend"; then
  log "Frontend startup failed. Check: $FRONTEND_LOG"
  cleanup_failed_start "frontend" "$FRONTEND_PORT" "$FRONTEND_SPAWN_FILE" "$PID_DIR/frontend.pid"
  exit 1
fi
finalize_listener_start "frontend" "$FRONTEND_PORT" "$FRONTEND_DIR" "$FRONTEND_SPAWN_FILE" "$PID_DIR/frontend.pid" || exit 1

if ! check_admin_login; then
  log "Restarting frontend because the Vite API proxy is not healthy."
  stop_port "$FRONTEND_PORT" "frontend" || exit 1
  rm -f "$PID_DIR/frontend.pid" "$FRONTEND_VERSION_FILE"
  start_frontend || exit 1
  if ! wait_for_url "http://127.0.0.1:$FRONTEND_PORT/" "Frontend"; then
    cleanup_failed_start "frontend" "$FRONTEND_PORT" "$FRONTEND_SPAWN_FILE" "$PID_DIR/frontend.pid"
    exit 1
  fi
  finalize_listener_start "frontend" "$FRONTEND_PORT" "$FRONTEND_DIR" "$FRONTEND_SPAWN_FILE" "$PID_DIR/frontend.pid" || exit 1
  if ! check_admin_login; then
    cleanup_failed_start "frontend" "$FRONTEND_PORT" "$FRONTEND_SPAWN_FILE" "$PID_DIR/frontend.pid"
    exit 1
  fi
fi

if ! listener_matches_source "$BACKEND_PORT" "$BACKEND_DIR" "$PID_DIR/backend.pid"; then
  log "Backend source verification failed after startup."
  cleanup_failed_start "backend" "$BACKEND_PORT" "$BACKEND_SPAWN_FILE" "$PID_DIR/backend.pid"
  exit 1
fi
if ! listener_matches_source "$FRONTEND_PORT" "$FRONTEND_DIR" "$PID_DIR/frontend.pid"; then
  log "Frontend source verification failed after startup."
  cleanup_failed_start "frontend" "$FRONTEND_PORT" "$FRONTEND_SPAWN_FILE" "$PID_DIR/frontend.pid"
  exit 1
fi

log "PMS is available at http://127.0.0.1:$FRONTEND_PORT"
log "Verified frontend and backend source: $SOURCE_DIR ($SOURCE_BRANCH@$SOURCE_COMMIT)"
log "Logs:"
log "  Backend:  $BACKEND_LOG"
log "  Frontend: $FRONTEND_LOG"

release_start_lock
trap - EXIT HUP INT TERM

if [[ "${PMS_NO_PAUSE:-0}" != "1" && -t 0 ]]; then
  printf "\nPress Enter to close this window..."
  read -r
fi
