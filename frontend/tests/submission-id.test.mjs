import assert from 'node:assert/strict'
import {newSubmissionId} from '../src/utils/submissionId.ts'
const values=new Set(Array.from({length:100},()=>newSubmissionId()))
assert.equal(values.size,100)
assert.ok([...values].every(value=>/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(value)))
console.log('Submission IDs work without secure-context randomUUID')
