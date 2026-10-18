import assert from 'node:assert/strict'
import {test} from 'node:test'
import * as fields from '../src/views/project/offlineArchiveFields.ts'
test('positive integer quantity rejects zero negative fractional and overflow without rewriting',()=>{
 assert.equal(typeof fields.archiveQuantityError,'function')
 for(const value of [0,-1,1.5,1000000000000,NaN,Infinity,true,'abc']) assert.ok(fields.archiveQuantityError(value))
 for(const value of [1,2,'2.00000000',999999999999]) assert.equal(fields.archiveQuantityError(value),null)
})
test('unchanged historical invalid quantity does not block editing another field',()=>{
 assert.equal(typeof fields.archiveQuantityError,'function')
 assert.equal(fields.archiveQuantityError(-1,'-1.00000000',true),null)
 assert.ok(fields.archiveQuantityError(-2,-1,true))
 assert.equal(fields.archiveQuantityError(1,-1,true),null)
 assert.equal(fields.archiveQuantityError(null),null)
})
