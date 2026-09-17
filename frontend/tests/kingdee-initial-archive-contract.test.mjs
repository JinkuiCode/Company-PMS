import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const archive = readFileSync(new URL('../src/views/project/ProjectArchive.vue', import.meta.url), 'utf8')

assert.match(archive, /待补全名称/, 'Nameless historical archives must be visibly incomplete')
assert.match(archive, /key: 'data_origin', label: '档案来源'/, 'Archive drawer must show provenance')
assert.match(archive, /kingdee_initial: '金蝶期初'/, 'Historical provenance must have a readable label')
assert.match(archive, /historical: '金蝶历史档案'/, 'Historical rows must not look newly synchronized')

console.log('kingdee initial archive UI contract passed')
