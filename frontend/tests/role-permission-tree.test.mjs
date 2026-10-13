import assert from 'node:assert/strict'
import { rolePermissionTree, canonicalPermissionIds, selectedPermissionLeaves } from '../src/views/system/role-permission-tree.ts'
const root={id:10,parent_id:0,menu_type:'C',menu_name:'问题提报',permission_code:'feedback:view',status:1,children:[{id:11,parent_id:10,menu_type:'B',menu_name:'新增',permission_code:'feedback:add'}]}
const tree=rolePermissionTree([root])
assert.equal(tree[0].children[0].permission_code,'feedback:view')
assert.equal(tree[0].children[0].menu_name,'查看')
assert.equal(tree[0].children[0].id,-10)
assert.deepEqual(canonicalPermissionIds([-10,10,11]),[10,11])
assert.deepEqual(selectedPermissionLeaves([10],[-10,11]),[-10])
assert.deepEqual(selectedPermissionLeaves([10,11],[-10,11]),[-10,11])
assert.equal(root.children.length,1)
const old={...root,permission_code:'feedback:list',children:[{id:21,parent_id:10,menu_type:'B',permission_code:'feedback:view'}]}
assert.equal(rolePermissionTree([old])[0].children.length,1)
console.log('Role tree passed: explicit existing view, view-only restoration, canonical IDs, no action grant')
