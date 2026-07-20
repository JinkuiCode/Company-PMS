import assert from 'node:assert/strict'
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'

const scriptUrl = new URL('../../start-pms.command', import.meta.url)
const scriptPath = fileURLToPath(scriptUrl)
const repoRoot = dirname(scriptPath)
const script = readFileSync(scriptUrl, 'utf8')

assert.match(script, /ACTIVE_SOURCE_FILE=.*active-source/, 'Launcher should persist the selected source tree')
assert.match(script, /SOURCE_STATE_FILE=.*active-source\.state/, 'Launcher should remember that source selection was initialized')
assert.match(script, /PMS_RUNTIME_DIR/, 'Launcher should allow isolated runtime diagnostics')
assert.match(script, /PMS_SOURCE_DIR/, 'Launcher should allow an explicit source tree override')
assert.match(script, /resolve_source_dir/, 'Launcher should resolve the configured source before starting services')
assert.match(script, /validate_source_dir/, 'Launcher should reject incomplete or missing source trees')
assert.match(script, /process_cwd/, 'Launcher should inspect the working directory of an existing listener')
assert.match(script, /ensure_listener_source/, 'Launcher should verify that an existing listener belongs to the selected source')
assert.match(script, /record_listener_pid/, 'Launcher should record the actual listening process instead of only the spawned parent')
assert.match(script, /BACKEND_VERSION_FILE=.*backend\.version/, 'Launcher should persist the backend source commit')
assert.match(script, /FRONTEND_VERSION_FILE=.*frontend\.version/, 'Launcher should persist the frontend source commit')
assert.match(
  script,
  /listener_matches_source\(\)[\s\S]*pid_file_value "\$version_file"[\s\S]*SOURCE_COMMIT/,
  'Launcher should not reuse a process started from an older commit in the same worktree',
)
assert.match(script, /START_LOCK_DIR=.*start\.lock/, 'Launcher should serialize concurrent double-click starts')
assert.match(script, /acquire_start_lock/, 'Launcher should acquire its start lock before changing processes')
assert.match(script, /release_start_lock/, 'Launcher should release its start lock on every exit path')
assert.match(script, /cleanup_failed_start/, 'Launcher should clean up processes left by a failed health check')
assert.match(
  script,
  /acquire_start_lock\s*\|\|\s*exit 1[\s\S]*persist_source_state/,
  'Launcher should acquire the lock before persisting source state or changing runtime state',
)
assert.ok(
  script.includes('printf "%s\\n" "$!" > "$BACKEND_SPAWN_FILE"'),
  'Launcher should track the backend process spawned by the current invocation',
)
assert.ok(
  script.includes('printf "%s\\n" "$!" > "$FRONTEND_SPAWN_FILE"'),
  'Launcher should track the frontend process spawned by the current invocation',
)
assert.match(
  script,
  /log "  Frontend:[^\n]*"\s+release_start_lock\s+trap - EXIT HUP INT TERM\s+if \[\[ "\$\{PMS_NO_PAUSE/,
  'Launcher should release its lock before waiting for the terminal window to close',
)
assert.doesNotMatch(
  script,
  /already listening, leaving PID .* running/,
  'Launcher must not blindly reuse any process occupying a PMS port',
)
assert.match(script, /RUNTIME_DIR\/data\/pms-dev\.db/, 'Launcher should keep SQLite data independent from temporary worktrees')
assert.match(script, /bootstrap\.\$\$/, 'Launcher should seed SQLite through a process-scoped temporary database')
assert.match(script, /mv -f "\$seed_target" "\$SQLITE_DB_PATH"/, 'Launcher should publish a completed SQLite backup atomically')
assert.match(script, /git -C "\$SOURCE_DIR" rev-parse --abbrev-ref HEAD/, 'Launcher should report the selected branch')
assert.match(script, /git -C "\$SOURCE_DIR" rev-parse --short HEAD/, 'Launcher should report the selected commit')
assert.match(script, /PMS_STATUS_ONLY/, 'Launcher should provide a non-destructive status mode for diagnostics')

const runStatus = (runtimeDir, extraEnv = {}) => spawnSync('zsh', [scriptPath], {
  cwd: repoRoot,
  encoding: 'utf8',
  env: {
    ...process.env,
    PMS_RUNTIME_DIR: runtimeDir,
    PMS_STATUS_ONLY: '1',
    ...extraEnv,
  },
})

const testRoot = mkdtempSync(resolve(tmpdir(), 'pms-launcher-contract-'))
try {
  const configuredRuntime = resolve(testRoot, 'configured')
  mkdirSync(configuredRuntime, { recursive: true })
  writeFileSync(resolve(configuredRuntime, 'active-source'), `${repoRoot}\n`)
  const configured = runStatus(configuredRuntime)
  assert.equal(configured.status, 0, configured.stderr)
  assert.match(configured.stdout, new RegExp(`Source:\\s+${repoRoot.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}`))

  const missingPointerRuntime = resolve(testRoot, 'missing-pointer')
  mkdirSync(missingPointerRuntime, { recursive: true })
  writeFileSync(resolve(missingPointerRuntime, 'active-source.state'), 'initialized\n')
  const missingPointer = runStatus(missingPointerRuntime)
  assert.notEqual(missingPointer.status, 0, 'Initialized runtime must not silently fall back when active-source is missing')
  assert.match(missingPointer.stderr, /active source configuration is missing/i)

  const invalid = runStatus(resolve(testRoot, 'invalid'), { PMS_SOURCE_DIR: resolve(testRoot, 'not-a-source') })
  assert.notEqual(invalid.status, 0, 'Invalid explicit source should fail')
  assert.match(invalid.stderr, /does not exist/i)
} finally {
  rmSync(testRoot, { recursive: true, force: true })
}

console.log('startup launcher contract passed')
