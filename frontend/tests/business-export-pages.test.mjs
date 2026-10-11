import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

for (const file of ['ProjectList', 'ProjectProgress']) {
  const source = readFileSync(new URL(`../src/views/project/${file}.vue`, import.meta.url), 'utf8')
  assert.ok(source.includes('BusinessExportControl'), `${file} must offer business export`)
  assert.ok(source.includes('businessExportSnapshot(queryApplied.value, columnFilters.value, gridApi.value)'), `${file} exports applied conditions, not the draft or current page`)
  assert.ok(source.includes(':snapshot="exportSnapshot"'))
  assert.ok(source.includes(':disabled="!columnContext.ready?.()"'), `${file} cannot export an unsubmitted/incomplete result`)
  assert.ok(source.includes(file === 'ProjectList' ? ':resource="{kind:\'projects\'}"' : ':resource="{kind:\'tasks\',projectId}"'))
  assert.ok(!source.includes('ReportExportControl'), 'Business export must not create an ERP report job')
}
console.log('business export pages passed: submitted full result state, project task identity and ready guard')
