# 2026-10-16 两项表单规范遗留本机收尾

用户明确批准“同意，仅本机修复这两项”。本批只处理前一批已确认的检查口径和版本通知页单个控件，不扩大到其他页面或后台。

## 已实施

1. `frontend/tests/form-system-contract.test.mjs`采用独立测试辅助函数`tests/helpers/form-style-scope.mjs`：认可原共享根及已批准的查询密度前缀，逐项检查顶层逗号分隔选择器；伪同名、业务页前缀和混入其他作用域仍拒绝。不修改共享CSS或放宽业务页样式覆盖规则。
2. `frontend/src/release-center/ReleaseCenter.vue`仅导入PmsCheckboxControl、替换unknown结果核查的一个原始勾选框并补aria-label。原因、勾选、unknown条件、忙碌禁用、按钮判断、权限及接口均保持；没有额外管理员控件或真实授权。

旧源文件副本保留于`outputs/form-compliance-20261016/ReleaseCenter.before.vue`。页面业务说明和人工核查规则没有变化，不为技术控件替换添加冗余业务文案。

## 验证

完整命令、退出码及当前源文件SHA256见`outputs/form-compliance-20261016/verification.json`。

- 新增2项范围测试覆盖6个允许、8个拒绝样例，先RED后GREEN。原始全局接入RED明确指向ReleaseCenter，替换后GREEN。
- `checks.json`共8组命令均退出0：新样式范围测试、全局表单契约、全局控件接入、表单布局、style/list/system三项必需规范和npm run build。构建仅已有分包大小警告。
- `browser.log`真实Vue组件、全模拟API通过：unknown缺原因或缺人工核查都不可提交；键盘Space可勾选；处理中输入和勾选禁用；模拟503失败保留原因及勾选，可再次提交；waiting/failed仅保留原原因要求；移除模拟重试权限后无按钮，普通用户无投递管理区。
- 两次模拟POST核对完整请求体`reason/checked_not_received`，没有向真实邮件或业务API发请求；非本机来源被测试路由阻止。
- 初次截图命中进入动画，补用禁用动画的截图方式得到清晰证据，见`unknown-confirm.jpg`；没有为截图改页面样式。
- 独立只读审查未发现本批实质缺陷、明显测试假阳性或范围越界，独立复跑2项测试及表单契约退出0。

此前共享模块记录中的两个既有失败已由本批解决，历史日志不删除。全局控件接入检查通过，不等于四项新共享行为已在所有旧页面迁移，也不等于全系统权限实测全部完成。

## 运行、版本及回退边界

只重启本机5174前端清除旧预览缓存；8000受控后端、真实配置、数据库及授权保持。没有真实发信、重试邮件、金蝶写入或正式环境访问/部署，不发布升级通知。

当前分支`codex/pms-unified-query`、HEAD`ae23468cd6f4130be21ff76a31443a2e54ec4440`，本批无提交、master合并、GitHub推送或PR。混合工作区与前批成果保留。回退仅还原该单控件/import与测试适配，不全量重置工作区；无需数据库回退。
