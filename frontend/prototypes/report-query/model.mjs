export const clone = value => JSON.parse(JSON.stringify(value))
export const labels = { contains: '包含', notContains: '不包含', eq: '等于', ne: '不等于', starts: '开头是', ends: '结尾是', gt: '大于', ge: '大于等于', lt: '小于', le: '小于等于', before: '早于', after: '晚于', between: '介于', in: '属于', notIn: '不属于', empty: '为空', notEmpty: '不为空' }
export function operators(type) {
  return [...({ text: ['contains', 'notContains', 'eq', 'ne', 'starts', 'ends'], number: ['eq', 'ne', 'gt', 'ge', 'lt', 'le', 'between'], date: ['eq', 'before', 'after', 'between'], select: ['eq', 'ne', 'in', 'notIn'] }[type] || []), 'empty', 'notEmpty']
}
export function matches(actual, op, value, end) {
  const empty = actual === null || actual === undefined || actual === ''
  if (op === 'empty') return empty
  if (op === 'notEmpty') return !empty
  if (empty) return false
  const a = String(actual).toLowerCase(), v = String(value).toLowerCase()
  if (op === 'contains') return a.includes(v)
  if (op === 'notContains') return !a.includes(v)
  if (op === 'starts') return a.startsWith(v)
  if (op === 'ends') return a.endsWith(v)
  if (op === 'in' || op === 'notIn') { const hit = (value || []).map(String).includes(String(actual)); return op === 'in' ? hit : !hit }
  if (op === 'eq') return a === v
  if (op === 'ne') return a !== v
  if (op === 'gt' || op === 'after') return actual > value
  if (op === 'ge') return actual >= value
  if (op === 'lt' || op === 'before') return actual < value
  if (op === 'le') return actual <= value
  return op === 'between' && actual >= value && actual <= end
}
export function validate(report, draft) {
  if (report === 'stock' && !draft.material?.trim()) return '请填写物料'
  if (report === 'stock' && !draft.organizations?.length) return '请选择至少一个库存组织'
  if (report === 'stock' && draft.dates?.length !== 2) return '请选择日期范围'
  if (draft.dates?.length === 2 && draft.dates[0] > draft.dates[1]) return '开始日期不能晚于结束日期'
  if (report === 'purchase' && draft.dates?.[0] < '2026-01-01') return '采购申请日期不能早于2026-01-01'
  for (const c of draft.conditions || []) {
    if (!operators(c.type).includes(c.op)) return '筛选运算符与字段类型不匹配'
    if (['empty', 'notEmpty'].includes(c.op)) continue
    if (c.value === '' || c.value === null || c.value === undefined || (Array.isArray(c.value) && !c.value.length)) return '请补全筛选值'
    if (c.op === 'between' && (c.end === '' || c.end == null || c.value > c.end)) return '请填写有效区间，起点不能大于终点'
  }
  return ''
}
export function createSession(initial) {
  return { draft: clone(initial), applied: null,
    get dirty() { return this.applied !== null && JSON.stringify(this.draft) !== JSON.stringify(this.applied) },
    restore(value) { this.draft = clone(value) }, apply() { this.applied = clone(this.draft) } }
}
export const organizations = [{ value: 1, label: '8吋半导体' }, { value: 2, label: 'Single' }]
export const stocks = [{ value: '研发仓', label: '研发仓', org: 1 }, { value: '半导体仓', label: '半导体仓', org: 1 }, { value: '装配仓', label: '装配仓', org: 2 }]
const field = (key, label, type = 'text', width = 140, options) => ({ key, label, type, width, options })
const materialFields = [field('material_code', '物料编码', 'text', 150), field('material_name', '物料名称', 'text', 130), field('spec', '规格型号', 'text', 170)]
const organizationField = field('organization', '库存组织', 'select', 125, organizations)
const stockField = field('stock', '仓库', 'select', 120, stocks)
const stateField = field('state', '库存状态', 'select', 100, [{ value: '可用', label: '可用' }, { value: '待检', label: '待检' }])
export const reports = {
  inventory: { title: '即时库存', subtitle: '库存余额与分布', fields: [...materialFields, organizationField, stockField, stateField, field('unit', '库存单位', 'text', 85), field('qty', '库存数量', 'number', 120), field('batch', '批号'), field('note', '备注', 'text', 210)] },
  purchase: { title: '采购进度', subtitle: '采购申请到入库', fields: [field('project', '项目编号', 'text', 140), field('bill', '申请单编号', 'text', 145), field('date', '申请日期', 'date', 120), ...materialFields, field('qty', '申请数量', 'number', 110), field('ordered', '累计下单数量', 'number', 125), field('received', '累计入库数量', 'number', 125), field('supplier', '供应商', 'text', 155), field('progress', '采购进度', 'select', 115, ['未下单', '部分下单', '待入库', '已完成'].map(value => ({ value, label: value })))] },
  stock: { title: '物料收发明细', subtitle: '库存流转追溯', fields: [field('material_code', '物料编码', 'text', 150), field('material_name', '物料名称', 'text', 120), field('date', '日期', 'date', 120), field('bill_name', '单据名称', 'text', 130), field('bill', '单据编号', 'text', 150), stockField, stateField, field('unit', '库存单位', 'text', 85), field('opening', '期初', 'number', 100), field('income', '收入', 'number', 100), field('issue', '发出', 'number', 100), field('balance', '结存', 'number', 100)] },
}
export const defaultDraft = report => ({ material: '', organizations: [], stock: '', dates: report === 'stock' ? ['2026-09-01', '2026-09-24'] : [], progress: '', conditions: [] })
export function dataFor(report) {
  return Array.from({ length: 68 }, (_, i) => {
    const org = i % 3 === 2 ? 2 : 1
    const base = { id: i + 1, material_code: ['180102020045', '170602100148', '180201080012'][i % 3], material_name: ['PFA管', '六角螺母', '隔膜阀'][i % 3], spec: ['外径6.35 × 壁厚1.0 mm', 'M6 / SUS304', 'DN15 / 气动常闭'][i % 3], organization: org, stock: stocks[i % 3].value, state: i % 7 === 0 ? '待检' : '可用', unit: ['米', '个', '只'][i % 3], qty: i % 9 === 0 ? 0 : i % 11 === 0 ? null : (i + 1) * 6.25, batch: `B202609${String(i % 20 + 1).padStart(2, '0')}`, note: i % 2 === 0 ? '项目备料' : null, project: `A-2026${String(i % 8 + 21)}`, bill: `CGSQ202609${String(i + 1).padStart(4, '0')}`, date: `2026-09-${String(i % 24 + 1).padStart(2, '0')}`, ordered: i % 4 ? 80 : 0, received: i % 4 === 3 ? 80 : i % 4 === 2 ? 40 : 0, supplier: ['示例供应商甲', '示例供应商乙'][i % 2], progress: ['未下单', '部分下单', '待入库', '已完成'][i % 4] }
    if (report !== 'stock') return base
    const incoming = i % 2 === 0
    return { ...base, material_code: '180102020045', material_name: 'PFA管', unit: '米', organization: org, bill: `DOC202609${String(i + 1).padStart(4, '0')}`, bill_name: incoming ? '直接调拨单' : '生产领料单', opening: null, income: incoming ? 6 : 0, issue: incoming ? 0 : 6, balance: incoming ? 6 : 0 }
  })
}
export function queryRows(report, query) {
  return dataFor(report).filter(row => {
    if (query.material && !`${row.material_code} ${row.material_name} ${row.spec}`.toLowerCase().includes(query.material.trim().toLowerCase())) return false
    if (query.organizations.length && !query.organizations.includes(row.organization)) return false
    if (query.stock && row.stock !== query.stock) return false
    if (query.progress && row.progress !== query.progress) return false
    if (query.dates?.length === 2 && (row.date < query.dates[0] || row.date > query.dates[1])) return false
    return query.conditions.every(c => matches(row[c.field], c.op, c.type === 'number' && c.value !== null ? Number(c.value) : c.value, c.type === 'number' ? Number(c.end) : c.end))
  })
}
