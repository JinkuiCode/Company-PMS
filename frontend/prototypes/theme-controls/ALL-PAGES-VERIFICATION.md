# 三主题全页面开发验收

日期：2026-10-19。工作区：`/Users/jin/.codex/worktrees/pms-theme-ui/PMS`，detached基线 `564653da4f1461eb985515517ece697a1c378793`，未提交。批准依据：用户明确要求按已确认方案继续三张报表和其他页面，不在试点后等待“继续”，暂不部署正式环境。

## 实际完成

- 实际App/布局接入独立主题模块，办公蓝、青绿、石墨统一驱动收起及展开态；不是逐页复制皮肤。用户/环境偏好隔离，刷新和同来源页签同步；公开说明及登录仅共享无身份外观提示。
- 采购总/明细、即时库存、收发明细使用同一入口。采购进度复用独立组件，原行数和比率口径不改；红低于50%、黄50%至未完成、绿真正完成。2499/2500显示100.0%但黄色，原计数可通过悬停和辅助技术读取。
- 项目档案、项目/任务进度、草稿、问题提报、仪表盘及管理页面接入共享适配。清理受影响页面旧私有配色；图表订阅同一主题，不改变数据。
- 分页改用已有统一选择控件，仍为15/20/50/100/200/300/500及26px外高，事件仍传数字；现有浏览器脚本的原生select调用随控件适配。
- 字体和紧凑布局保留；已更新页面说明中的进度颜色解释及开发标准。真实认证store、生产路由、请求层、后端、数据库和权限未改。

## 当前入口与隔离

- 全页面：<http://127.0.0.1:5184/application-pilot.html>，实际App/布局/业务页面置于模拟OA iframe，可通过图标菜单悬停切页。
- 档案专项：<http://127.0.0.1:5184/archive-pilot.html>；原控件/进度样稿入口继续保留。
- 5184独立Vite无API代理。预览专用身份、内存路由及失败关闭的模拟接口仅在预览配置生效；生产构建使用原认证和路由。模拟数据不含真实用户凭据或业务记录。
- 主目录5174/8000及正式环境不替换、不重启。临时5185生产构建服务已在档案回归后关闭；5184保留。

## 当前验证及退出状态

以下命令均在本工作区`frontend/`执行，最终退出码均为0。细项结果和截图保留于`outputs/theme-application/`及`outputs/theme-module/`。

| 命令 | 结果 |
| --- | --- |
| `node --test tests/theme-system.test.mjs tests/theme-rollout.test.mjs tests/theme-progress-component.test.mjs tests/theme-task-progress.test.mjs tests/purchase-overview-layout.test.mjs tests/report-identity-pages.test.mjs tests/report-draft-submit.test.mjs tests/report-query-state.test.mjs tests/stock-detail-state.test.mjs tests/project-progress-workbench-contract.test.mjs tests/page-guide-tab.test.mjs tests/form-system-contract.test.mjs tests/form-system-layout-contract.test.mjs tests/form-system-adoption-contract.test.mjs` | 72/72，零失败 |
| `node tests/pagination-options.test.mjs` | 5/5；七种条数、数值事件、26px和键盘选择 |
| `node tests/style-contract.test.mjs` | passed；最终工具页语义色修订后复跑 |
| `node tests/list-standard-contract.test.mjs` | passed |
| `node tests/system-ui-consistency-contract.test.mjs` | passed |
| `node tests/archive-filter-contract.test.mjs` | passed |
| `npm run build` | 实际前端类型及生产构建通过 |
| `./node_modules/.bin/vue-tsc -p prototypes/theme-controls/tsconfig.json --noEmit` | 隔离预览类型通过 |
| `./node_modules/.bin/vite build --config prototypes/theme-controls/vite.config.mjs` | 四个独立入口构建通过 |
| `node tests/theme-application-browser.mjs` | 27组检查，18个业务/管理路由三主题及深交互；errors/unknown为空 |
| `node tests/theme-embedded-browser.mjs` | 1920/1366/768/390四视口，各三主题；44px头、64px侧栏、悬停子菜单、无文档溢出或业务网络请求 |
| `node tests/theme-secondary-pages-browser.mjs` | 两个真实仪表盘画布包含每套主题目标像素；无权页/工具页继承；登录三主题无认证请求 |
| `node tests/theme-public-guide-browser.mjs` | 凭据读取抛错时公开说明正常显示，errors/API为空 |
| `env THEME_PILOT_BASE=http://127.0.0.1:5185 node tests/theme-archive-pilot-browser.mjs` | 最终生产构建：三主题弹层、非默认查询/排序/分页/列宽/选择/滚动、草稿、审批预览、窄屏和存储完全禁用，共8组通过 |

全应用业务路由：三报表、项目档案、项目进度、草稿管理、问题提报、仪表盘、用户、角色、参数、枚举、字典、字段规则、产品线、同步、操作日志、项目任务填报。查询、日期、引用、多选、树、分页、漏斗、用户/角色抽屉均展开验证。切换不新增业务请求，报表进入仍待查询；档案未保存草稿和表格状态保持。

初始测试曾暴露实际进度/公开外观功能缺失（RED），随后实现转为GREEN。独立复核的四项发现均关闭：公开页认证store初始化、任务均值取整提前变绿、进度可访问名称及未完成解释、旧分页断言。前三项均有原症状回归；任务颜色回归另做撤回实现失败/恢复通过。复核者只读复跑两项回归2/2、退出0；未以其口头结论替代本次浏览器证据。

截图示例：`embedded-1366-teal.png`、`embedded-390-graphite.png`、`inventory-field-*`、`stock-calendar-*`、`feedback-draft-*`、`user-tree-*`、`role-scope-*`、`dashboard-canvas-*`。机器结果分别为`browser-result.json`、`embedded-result.json`、`secondary-pages-result.json`、`public-guide-credential-guard.json`和档案目录的`browser-result.json`。源码与结果摘要记录在`verification-manifest.json`。

## 未宣称的范围

- 使用macOS Edge隔离浏览器及内置浏览器、模拟记录和OA外壳；不声称Windows字体栅格、真实OA/SSO或正式业务后端已验证。SSO页面仅沿用原流程并令牌化品牌边框，没有执行真实跳转或生成凭据。
- 原有AG Grid旧选择API提示、工具页既有table/tr开发警告和构建大包提示仍存在；未因主题工作重构无关行为。无未解决的本批页面运行异常。
- 旧业务浏览器脚本仅适配分页控件调用，未宣称整套旧端到端脚本全部重跑；本次实际交互由上述新浏览器套件和相关既有契约覆盖。
- 开发交付不包含主目录集成、提交、主分支合并、GitHub推送、正式发布或数据库升级。其他聊天后续变更集成时须按固定候选复核冲突与适用回归，不能把本工作区截图当成正式界面已更新。
