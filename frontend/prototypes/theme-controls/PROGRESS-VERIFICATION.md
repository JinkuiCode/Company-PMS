# 进度与异常配色样稿

日期：2026-10-19。用户要求把上一轮进度阶段和异常配色建议制作成独立样稿。入口：<http://127.0.0.1:5184/?scene=progress>。

## 当前修订：红、黄、绿

用户随后明确要求最低进度红色、中间黄色、完成绿色，已在同一独立样稿改为：0%至不足50%红色，50%至不足100%黄色，完全完成绿色。0%空进度保留，数值标红；异常色不变。下方首版配色和摘要为历史记录，不代表当前ProgressPreview.vue。

本次验证：三项规定前端契约、项目构建和独立样稿构建退出0。隔离Edge三主题实际颜色、50%分界、0%真实空长度及99.96%显示100.0%仍黄色通过，390宽度无外层溢出、页面错误为空。结果为 `outputs/theme-controls/progress-ryg-result.json`，截图为 `progress-ryg-blue.png`、`progress-ryg-teal.png`、`progress-ryg-graphite.png`、`progress-ryg-390.png`。内置浏览器已刷新到本版。

当前ProgressPreview.vue SHA256：`a380a4e43ac44e2eef8cabaacc7d26fed91169273f17b4d56b85ff06ee6b7e51`。

2026-10-19用户查看红黄绿修订后回复“同意”，本修订成为已确认的进度配色基线：不足50%红色，50%至不足100%黄色，原始数据完全完成绿色；0%不虚填，显示四舍五入不提前改变完成状态。后续报表接入沿用此版。本确认记录只固定当前样稿基线，主题模块和页面迁移仍按团队登记的后续批次实施。

## 本次实际调整

- 新增 `ProgressPreview.vue`，复用已有三主题外壳和语义令牌。App.vue增加“进度与异常”页签及直达参数；preview.css仅补页签横向滚动。
- 8条虚构项目覆盖未开始、前期、持续推进、完成、待核对、已确认错误、超量入库、99.96%四舍五入边界。
- 进度色不跟随界面主题变化；文字和图标同时表达含义。待核对及提醒使用琥珀色，已确认错误使用红色，0异常单元格留空。
- 两项采购比率沿用现有行数口径，部分下单不计转单分子，待核对计分母但不计分子。修正上一条文字方案中“100%完成且待核对行不为0”的错误例子；完成且有提醒使用独立超量入库示例。
- 数据错误和超量入库入口仅用于配色样稿，未增加正式报表字段或判断规则。

## 验证

- `vue-tsc -p prototypes/theme-controls/tsconfig.json --noEmit`：退出0。
- `style-contract.test.mjs`、`list-standard-contract.test.mjs`、`system-ui-consistency-contract.test.mjs`：全部退出0。
- `npm run build`：退出0；`vite build --config prototypes/theme-controls/vite.config.mjs`：退出0。包体警告与首批相同。
- 一次性本地Node/Playwright检查：三主题阶段色、0/50/100分界、原始比率与显示四舍五入、待核对/错误/超量三个原因弹窗通过，退出0。1920/1366/768/390无外层页面溢出，窄屏保留异常数字示例。页面错误和外部/业务请求均为空。
- 初次检查在可选色觉模拟API处中止，页面断言已执行；改用当前依赖声明的CDP `Emulation.setEmulatedVisionDeficiency` 后完整复验退出0。保留绿色色觉异常模拟图，并以文字/图标补充颜色信号。
- 浏览器：macOS Edge 155.0.4283.62。JSON结果为 `outputs/theme-controls/progress-result.json`；`progress-blue.png`、`progress-teal.png`、`progress-graphite.png`、`progress-error-*.png`、`progress-layout-*.png`、`progress-color-vision.png`为实际截图。用户内置浏览器已展示直达入口。

## 首版SHA256（历史）

```text
11c41f1ef8f3659c0fe11b54c373ca8b5dab29de9b378d273a63901e12b2daf9 ProgressPreview.vue
1f414c45cb9e51d47ea1e566766f075fff41ad0c658035d72297f7968c2f12d3 App.vue
15618d885e65a825e44d49743218ba470bfd485a2e575456a6ad92bd329338e0 preview.css
```

独立样稿阶段，现有业务源码、后端、数据库及正式环境未修改；无提交、合并、推送或部署。真实Windows/OA渲染未在本次验证。
