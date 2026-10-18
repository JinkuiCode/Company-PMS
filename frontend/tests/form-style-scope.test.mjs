import assert from 'node:assert/strict'
import {test} from 'node:test'
import {existsSync} from 'node:fs'
const url=new URL('./helpers/form-style-scope.mjs',import.meta.url)
const mod=existsSync(url)?await import(url.href):{}
function accepted(selector){assert.equal(typeof mod.isFormSystemSelector,'function','表单样式范围检查必须可复用');return mod.isFormSystemSelector(selector)}
test('允许共享表单根及已批准的查询密度作用域',()=>{
 for(const selector of [
  '.pms-form-control .el-input__wrapper {',
  '.pms-form-grid .el-input__inner,',
  '.pms-form-control.is-error .el-select__wrapper {',
  '.pms-query-density .pms-form-control .el-select__wrapper {',
  '.pms-query-density .pms-form-control :is(.el-input__inner, .el-textarea__inner) {',
  '.pms-form-control [data-value=","] .el-input__inner {',
 ])assert.equal(accepted(selector),true,selector)
})
test('拒绝业务页面覆盖、伪同名和逗号混入未授权作用域',()=>{
 for(const selector of [
  '.archive-page .el-input__wrapper {',
  '.archive-page .pms-form-control .el-input__wrapper {',
  '.pms-query-density .el-select__wrapper {',
  '.pms-form-control-evil .el-input__wrapper {',
  '.pms-query-density-evil .pms-form-control .el-input__wrapper {',
  '.pms-form-control .el-input__wrapper, .archive-page .el-select__wrapper {',
  'body .pms-form-control .el-input__wrapper {',
  '',
 ])assert.equal(accepted(selector),false,selector)
})
