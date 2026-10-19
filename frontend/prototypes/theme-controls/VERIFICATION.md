# P04 控件状态样稿核验记录

日期：2026-10-19。工作区：`/Users/jin/.codex/worktrees/pms-theme-ui/PMS`。
基线：`564653da4f1461eb985515517ece697a1c378793`，detached HEAD。仅独立样稿，无提交或发布。

本记录固定于三主题控件首批交付，后续新增“进度与异常”后的App.vue和preview.css已变化，下方摘要不代表追加后的当前字节。新增配色样稿的当前验证见 `PROGRESS-VERIFICATION.md`。

## 结果

| 检查 | 结果 |
| --- | --- |
| `node --test tests/theme-controls.test.mjs tests/theme-controls-ui.test.mjs` | 5/5，退出0；缺失入口/模块的初始RED已记录 |
| `vue-tsc -p prototypes/theme-controls/tsconfig.json --noEmit` | 退出0 |
| `node tests/theme-controls-browser.mjs` | 三主题完整交互通过，退出0；无页面错误，无外部或业务接口请求 |
| `node tests/theme-controls-edge-cases.mjs` | 跨页签主题、树/空选项/加载/行内编辑、键鼠焦点/悬停、表格数字/日期、窄屏弹层通过，退出0 |
| `node tests/theme-controls-review.mjs` | 四项审查回归4/4，退出0；修复前四项均已实际复现 |
| `vite build --config prototypes/theme-controls/vite.config.mjs` | 当前样稿退出0；完整控件库包体警告，不是构建错误 |
| `style-contract.test.mjs` | 退出0 |
| `list-standard-contract.test.mjs` | 退出0 |
| `system-ui-consistency-contract.test.mjs` | 退出0 |
| `archive-filter-contract.test.mjs` | 退出0 |
| `npm run build` | 隔离工作区生产前端构建退出0；原业务源码未改变，构建产物未发布 |
| 正式源码边界 | `git diff --name-only -- frontend/src frontend/package.json frontend/package-lock.json backend` 为空 |

浏览器：macOS Edge 155.0.4283.62，隔离测试会话；内置浏览器已打开真实5184入口。
响应式覆盖：1920/1366/768/390 CSS像素宽。桌面双月日期，窄屏双月上下排列并滚动；已实际选择跨月区间。

## 本批修复

- 空选择值显式传null，避免可选布尔联合属性误显示false。
- 引用弹窗同一行输入及按钮统一32px；查询行保持24px。
- 校验成功反馈使用语义成功色，错误保留红色。
- 日期弹层窄屏宽高溢出均以失败断言复现，统一适配后横向/纵向边界及跨月点击通过。
- 独立代码审查发现四项P2：不完整/逆序日期缺少反馈、行内编辑未聚焦、跨页签换色后刷新回退、分页后排序。已分别复现并修复；复用既有查询校验及客户端排序模块，未修改共享源码。
- 查询日期错误保留上次结果；行内编辑点击即可键入，Esc恢复原值；主题跨页同步时同步URL；排序先于分页且本页漏斗仍仅作用于本页。
- 测试等待AG Grid翻页动画结束后核对唯一行，不以任取第一个匹配元素掩盖结果。

## 固定摘要

以下SHA256为最终功能文件，后续如变更需重新判断验证适用性：

```text
651031a859efa3925064f9e203a631a0e5de330bbe6863850baba19520536d59 App.vue
59700b25694dca0a2f8584b2b0f070e18529774995d1209907569513eea3b16f preview.css
fb3eb4ce4183a19fd63c1708f83f28f4f44e9bf6e9b62e50177a1dab0e5a83a5 theme.mjs
6fb439184f88fcd0c5e718eee82c8266a28b0e8aeab9e71ed9a52fcae1d807fa GridEditor.vue
```

## 交付边界

- 方案/列设置/侧栏仅承担外观展示，不计入真实业务方案管理或菜单导航验收；说明与README明确该限制。
- 没有接入真实用户偏好、后端、账号、数据库、权限或生产系统，未操作金蝶/OA。
- OA只是布局模拟；真实Windows/OA渲染和SSO未验证。本条是证据边界，不把用户本人验收列作本阶段AI待办。
- 本阶段完成的是独立交互样稿与验证，不等于P04全系统主题迁移完成。后续共享模块接入和页面迁移按总控的单一写入责任及分批范围执行；Git和生产操作不包含在本交付中。

机器结果：`outputs/theme-controls/browser-result.json`、`edge-cases-result.json`、`review-result.json`。同目录PNG为真实浏览器截图；早期failure图保留作为修复前证据，不作为当前验收图。
