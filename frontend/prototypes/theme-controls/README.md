# P04 三主题真实控件样稿

日期：2026-10-19。独立工作区基线：`564653da4f1461eb985515517ece697a1c378793`。

## 交付范围

本目录保留已确认三套配色的真实控件预览、实际档案试点，并在用户继续实施批准后接入实际应用的全部页面；仅本工作区开发实现，未部署正式系统。

## 全页面开发预览

- 入口：<http://127.0.0.1:5184/application-pilot.html>。模拟OA外壳内加载实际 `App.vue`、布局及业务页面，可通过64px图标栏悬停切换菜单。
- 三张报表、项目/任务、问题提报和管理页面共用 `src/theme-system/`，页头切换办公蓝、青绿和石墨；主目录5174不替换、不重启。
- 所有记录均为模拟数据。预览专用身份与请求适配、内存路由仅在本目录Vite配置中生效，未知请求拒绝，无API代理。生产认证、路由及请求层不改。
- 下文“frontend/src未改”和“仅样稿”等边界仅描述最初控件样稿批次，不适用于已批准的后续实际源码接入；分批证据分别保留，当前全页证据见 `ALL-PAGES-VERIFICATION.md`。

## 新增：共享模块与档案试点

- 入口：<http://127.0.0.1:5184/archive-pilot.html>。加载实际 `ProjectArchive.vue`，不是重画的静态档案表。
- 新共享模块：`src/theme-system/`，三主题令牌、按环境/用户记忆、切换入口、集中式弹层与表格适配。
- 使用64条明确的模拟档案、本地身份和内存适配器；未知请求拒绝，不连接业务后端。
- 本目录的Vite配置仅在试点中替换身份与请求依赖，正式认证、请求层及生产配置均不改。
- 完整证据与审查闭环见 `ARCHIVE-PILOT-VERIFICATION.md`；下文“frontend/src未改”等隔离描述仅指前一批控件样稿，不包括本次新建的独立主题模块。

- 入口：<http://127.0.0.1:5184/>。右上角切换办公蓝、青绿、石墨。
- 进度配色追加样稿：<http://127.0.0.1:5184/?scene=progress>，也可点击“进度与异常”。包含进度分段、琥珀提醒、红色已确认错误及可点击原因。
- 查询与引用：真实字段/条件下拉、引用弹窗、多选缩略、已选明细、本页漏斗、分页。
- 表单与状态：文本、选择、多选、树、日期、区间、数字、长文本、勾选、开关，含焦点、校验错误、加载、禁用和只读。
- 表格编辑：真实 AG Grid 的文本、产品线、数量和日期编辑；详情行内编辑和抽屉单独适配。
- 保留已确认浅色、Noto Sans SC、OA紧凑框架。OA外壳保持蓝色，不随PMS换色。
- 主题只写独立5184来源的预览偏好，支持刷新保留和同来源页签同步；演示档案修改只存内存，刷新即复原。

## 隔离边界

- 仅本目录、对应测试、工作区自己的验收记录与 `change.md` 有调整。现有 `frontend/src/`、主目录、后端、权限、数据库和正式服务器未修改。
- 使用24条虚构档案，不访问业务接口；Vite只监听127.0.0.1:5184，无API代理。
- 真实PMS组件从本工作区导入。主题映射和针对弹层的适配集中在 `theme.mjs` / `preview.css`，不散落进业务页。
- `preview.css` 对第三方弹层结构的适配只属于本预览。正式实施时须纳入共享表单/查询/主题适配模块，不能复制为逐页覆盖。
- “方案设置”“说明”只说明样稿范围；“列设置”为固定字段展示，不实现真实方案持久化、权限或列偏好业务。
- OA及PMS侧栏只展示嵌入布局和菜单外观，不提供真实业务导航，不计入本次功能验收。
- Git保留detached基线；无提交、合并、推送、部署。其他任务的工作区和服务保持原状。

进度色按用户追加要求改为红（0%至不足50%）、黄（50%至不足100%）、绿（完全完成），主题只改变界面外观。0%使用空进度和红色数值，不伪造填充长度。以原始行数判断完成，不以四舍五入后的显示值判断。采购待核对行仍计分母、不计两项比率分子；“完成且有提醒”用独立的超量入库示例展示。数据错误列和超量提醒仅用于配色讨论，尚未加入正式报表规则。

## 启动与停止

双击本目录 `start-preview.command`；使用独立终端运行。结束时在该终端按Ctrl+C，只停止5184样稿。

## 核验入口

以下命令均在本工作区 `frontend` 下运行：

```sh
node --test tests/theme-controls.test.mjs tests/theme-controls-ui.test.mjs
./node_modules/.bin/vue-tsc -p prototypes/theme-controls/tsconfig.json --noEmit
node tests/theme-controls-browser.mjs
node tests/theme-controls-edge-cases.mjs
node tests/theme-controls-review.mjs
./node_modules/.bin/vite build --config prototypes/theme-controls/vite.config.mjs
node tests/style-contract.test.mjs
node tests/list-standard-contract.test.mjs
node tests/system-ui-consistency-contract.test.mjs
node tests/archive-filter-contract.test.mjs
npm run build
```

浏览器结果与截图：工作区 `outputs/theme-controls/`。独立样稿构建：`.runtime/theme-controls-build/`。
本批执行结果、审查闭环和固定摘要见本目录 `VERIFICATION.md`。

当前验证使用macOS Edge隔离会话及内置浏览器。1920、1366、768、390是CSS视口宽度；OA为布局模拟，不代表真实OA门户、Windows字体栅格或SSO已验收。全局接入时仍须实际Windows/OA逐批验证。

## 后续集成顺序

保持已确认方案：共享主题令牌及持久偏好模块 → 项目档案试点 → 三个报表 → 其他页面，逐批核对真实展开态和业务行为。偏好须按实际环境/用户隔离，不能把预览用户或本地存储键直接用于正式系统。P04本阶段不擅自接入主目录、修改其他任务公用文件或进行生产发布。
