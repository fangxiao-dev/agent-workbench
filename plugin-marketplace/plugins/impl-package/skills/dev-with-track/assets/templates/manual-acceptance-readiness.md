## 人工验收就绪信息

<!-- 仅在 Planned Verification 存在 manual owner、且准备交给人验收时使用。写入 Execution Record judgment 或 canonical handoff；用于 3.6 Journey 取证时，记录作为 package 内 artifact 登记为 `journey-step` evidence。项目已有验证入口/测试身份目录时先引用它，没有再在对应行写明。 -->

- 通过标准与可观察结果：
- manual owner（谁人验、为什么必须人验）：
- 入口与最短路径（URL/route/command；有项目验证入口先引用；对应的 Journey step、角色、控件、操作入口与观察表面）：
- 走查人（登记为 `manualBy`）与截图（package 内路径，登记为该步 artifact）：
- 测试身份 / seed（有身份目录先引用，没有则直接写明）：
- mock / not-wired 边界：
- 承接的业务对象（Spec 该步“承接”非 `—` 时：本步 inputRef 与产出的 outputRef）：
- 失败反馈方式：
- environment（Spec 声明的字符串）：
- reset / teardown owner 与清理结果（如适用）：
- 读回（执行后如何确认数据与界面状态一致）：

何时必须人验：主观视觉与文案；只能由真实外部服务产生的行为；不可逆外部副作用；需要专业（税务/会计）判断的 oracle。
