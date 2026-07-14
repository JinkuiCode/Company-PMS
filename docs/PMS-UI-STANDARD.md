# PMS 前端界面规范

## 目标

PMS 面向企业内部高频使用，界面以项目档案和项目进度为基准：浅色、紧凑、清晰、可扫描。页面应优先提高信息辨识度和操作效率，不使用与业务无关的装饰。

## 字体与字号

- 中文正文统一使用项目内置 `Noto Sans SC`，入口为 `frontend/src/main.ts`，全局变量为 `--pms-font`。
- Element Plus 与 AG Grid 必须继承 `--pms-font`，页面不得单独声明系统字体栈。
- 常规正文和表格数据使用 `13px`，辅助信息和表头使用 `12px`，分区标题使用 `14px`，页面重点标题使用 `16px` 或 `18px`。
- 编号、字段编码等技术值使用 `.pms-code`，数字统计应使用等宽数字。

## 页面骨架

- 标准业务列表使用 `PmsDataList.vue`、`PmsListFilters.vue` 和 `useListFilters.ts`。
- 系统管理页根节点使用 `.pms-system-page`。
- 独立内容区使用 `.pms-surface-section`；双栏页面使用 `.pms-split-page`。
- 分区头部使用 `.pms-section-header`，标题和辅助信息分别使用 `.pms-section-title`、`.pms-section-meta`。
- 页面内不重复创建大面积卡片，也不使用重阴影和大圆角。

## 表格与筛选

- Element Plus 表格统一增加 `.pms-dense-table`，AG Grid 使用 `.pms-ag-grid`。
- 表头居中，行高保持约 `36-38px`；业务数据按语义对齐，金额和进度数值右对齐或居中。
- 筛选控件使用 `small` 尺寸，搜索、枚举筛选、清空操作保持在同一紧凑工具栏。
- 列多时必须提供可见横向滚动条；分页紧邻表格，不放到页面最底部。

## 控件与状态

- 新增、保存等主操作使用靛蓝主按钮；删除使用危险色；普通操作使用默认按钮或链接按钮。
- 状态统一使用 `.pms-status`、状态点及语义色，不在页面内另写一套胶囊标签。
- 图标优先使用 Element Plus 图标。数据库动态菜单使用的图标名称，必须同步注册到 `AppLayout.vue` 的 `iconMap`。
- 禁止使用 emoji 充当业务图标。

## 颜色与实现约束

- 颜色、边框、圆角、字号和阴影统一取自 `frontend/src/styles/pms-theme.css`。
- 页面局部样式不得重新使用 Element Plus 旧默认色（如 `#409EFF`、`#303133`）或复制新的字体声明。
- 新增页面先复用全局类和现有组件；只有业务特有布局才增加局部样式。
- 修改有效菜单页面后运行 `frontend/tests/system-ui-consistency-contract.test.mjs` 和生产构建。

## 操作日志展示

- 日志详情使用后端 `diff_items`，字段中文名由字段目录、项目总表注册表和统一覆盖映射解析。
- 前端不得维护另一套业务字段中文名映射；原始字段编码仅作为次级技术信息展示。
- 枚举、布尔值、空值和嵌套字段应由后端格式化为业务可读值。
