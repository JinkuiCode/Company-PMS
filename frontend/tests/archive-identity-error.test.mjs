import {test} from 'node:test'
import assert from 'node:assert/strict'
import * as validation from '../src/views/project/archiveDraftValidation.ts'
test('identity failures retain server message, field and bounded correction intent',()=>{
 assert.equal(typeof validation.archiveIdentityFailure,'function','shared identity failure parser is required')
 const read=detail=>validation.archiveIdentityFailure({response:{data:{detail}}})
 assert.deepEqual(read({code:'ARCHIVE_UNIQUE_CONFLICT',field_key:'serial_no',message:'序列号已占用'}),{field_key:'serial_no',message:'序列号已占用',allowCorrection:true})
 for(const code of ['ARCHIVE_SERIAL_BUSY','ARCHIVE_CODE_BUSY','ARCHIVE_SERIAL_UNAVAILABLE']) {
  const item=read({code,field_key:'serial_no',message:'请稍后重试；输入已保留'})
  assert.equal(item.allowCorrection,false);assert.equal(item.message,'请稍后重试；输入已保留')
 }
 assert.equal(read({code:'SOMETHING_ELSE',field_key:'serial_no'}),null)
 assert.equal(read('unstructured'),null)
})
