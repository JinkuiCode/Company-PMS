// Isolated design fixtures; no ERP or PMS API is called by this prototype.
export const states = [
  { value: 'not_ordered', label: '未下单', tone: 'info' },
  { value: 'ordering', label: '部分下单', tone: 'warning' },
  { value: 'receiving', label: '待入库', tone: 'info' },
  { value: 'complete', label: '已完成', tone: 'success' },
  { value: 'review', label: '数据待核对', tone: 'danger' },
]
export const projects = [
  ['A-202638', '晶圆清洗设备', '8吋Bench', '江苏亚电 / 8吋半导体', [3, 4, 5, 28, 0]],
  ['A-202638', '晶圆清洗设备', 'Single', '江苏亚电 / Single', [4, 2, 4, 6, 0]],
  ['SS-202603-02', '单片湿法工艺设备', 'Single', '江苏亚电 / Single', [0, 0, 0, 24, 0]],
  ['L_B-202608', '槽式清洗系统改造', '8吋Bench', '江苏亚电 / 8吋半导体', [8, 4, 6, 12, 2]],
  ['A-202639', '自动化搬运项目', '8吋Bench', '江苏亚电 / 8吋半导体', [0, 2, 10, 8, 0]],
  ['L_AS-202415', '设备维修与改造', 'Single', '江苏亚电 / Single', [9, 0, 0, 0, 1]],
  ['RD-202605', '工艺研发验证平台', '8吋Bench', '江苏亚电 / 8吋半导体', [0, 0, 2, 14, 0]],
  ['D-202655', '客户现场备件', 'Single', '江苏亚电 / Single', [0, 0, 0, 8, 0]],
  ['A-202626', '清洗机配套系统', '8吋Bench', '江苏亚电 / 8吋半导体', [2, 3, 4, 11, 0]],
  ['SA-202657', '售后耗材补充', 'Single', '江苏亚电 / Single', [1, 1, 2, 2, 0]],
  ['A-202640', '晶圆传送模块', '8吋Bench', '江苏亚电 / 8吋半导体', [0, 0, 0, 18, 0]],
  ['D-202654', '现场管路改造', 'Single', '江苏亚电 / Single', [2, 2, 3, 5, 0]],
].map(([code, name, product, organization, counts], i) => ({ id: `project-${i}`, code, name, product, organization, counts }))
const materials = [['180102020045', 'PFA管', 'Φ12 × 1 mm', '米'], ['170604040037', '卡套接头', '1/2英寸', 'Pcs'], ['180102020047', '气体过滤器', '标准型', 'Pcs'], ['180103010028', '电磁阀', '24V DC', 'Pcs'], ['180105020032', '密封圈', 'PTFE', 'Pcs']]
export const lines = projects.flatMap((p, pi) => {
  let serial = 0
  return p.counts.flatMap((count, si) => Array.from({ length: count }, () => {
    const n = serial++, material = materials[n % materials.length], requested = [20, 10, 8, 4, 12][n % 5]
    const ordered = si === 0 ? 0 : si === 1 ? requested / 2 : requested
    return { id: `${p.id}-${n}`, project_id: p.id, code: p.code, product: p.product,
      organization: p.organization, name: p.name, material_code: material[0], material: material[1], spec: material[2], unit: material[3],
      bill: `CGSQ${31020 - pi * 3 - Math.floor(n / 10)}`, line: n % 10 + 1,
      date: `2026-09-${String(1 + n % 24).padStart(2, '0')}`, status: si === 4 ? '审核中' : '已审核',
      requested, ordered, received: si === 3 ? requested : si === 2 ? requested / 2 : 0,
      progress: states[si].value, progress_label: states[si].label, tone: states[si].tone }
  }))
})
export function summarize(rows) {
  return projects.flatMap(p => {
    const own = rows.filter(r => r.project_id === p.id)
    if (!own.length) return []
    const counts = states.map(s => own.filter(r => r.progress === s.value).length)
    return [{ ...p, total: own.length, counts, percent: counts[3] / own.length * 100 }]
  })
}
