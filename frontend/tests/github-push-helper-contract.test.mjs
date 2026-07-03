import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const script = readFileSync(new URL('../../push-github.command', import.meta.url), 'utf8')

assert.match(
  script,
  /GIT_TERMINAL_PROMPT=0\s+"?\$GIT_BIN"?\s+push/,
  'push helper should not let git prompt for stale username/password before the script asks for a token',
)

assert.match(
  script,
  /credential reject/,
  'push helper should reject stale GitHub credentials before approving the newly entered token',
)

assert.match(
  script,
  /clear_github_credential/,
  'push helper should use one cleanup path for GitHub credentials',
)

assert.match(
  script,
  /推送仍然失败/,
  'push helper should explain token or permission failure after retry',
)

assert.match(
  script,
  /repo 权限|Contents 读写权限/,
  'push helper should tell the user which GitHub token permissions are required',
)

console.log('github push helper contract passed')
