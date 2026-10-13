type PermissionNode = {
  id: number
  parent_id?: number
  menu_type: string
  menu_name?: string
  permission_code?: string
  status?: number
  children?: PermissionNode[]
}

export function rolePermissionTree(nodes: PermissionNode[]): PermissionNode[] {
  return nodes.map(node => {
    const children = rolePermissionTree(node.children || [])
    if (node.menu_type === 'C' && node.permission_code?.endsWith(':view') && children.length
        && !children.some(child => child.permission_code === node.permission_code)) {
      // A negative UI key represents the existing menu permission, never a new DB node.
      children.unshift({ id: -node.id, parent_id: node.id, menu_type: 'B', menu_name: '查看',
        permission_code: node.permission_code, status: node.status })
    }
    return { ...node, children }
  })
}

export function canonicalPermissionIds(keys: number[]): number[] {
  return [...new Set(keys.map(key => Math.abs(key)))]
}

export function selectedPermissionLeaves(ids: number[], leaves: number[]): number[] {
  const selected = new Set(ids)
  return leaves.filter(key => selected.has(Math.abs(key)))
}
