# 走查记录 <旅程 ID> <runId>

走查人：<Owner 或执行 agent 的标识；登记为 `manualBy`>
受验 HEAD：
environment：<Spec 声明的字符串>
取证方式：浏览器走查 | Playwright（Spec 的「取证：」行原文）
执行者变体：主路径 | <Spec「Journey 变体」中的变体执行者>（必验 | 非必验）| 探索性抽查：<身份>（主路径以外的记录不登记 evidence，runId 与主路径分开）
必验变体勾对：<按覆盖表的必验清单逐项写 `[x] J<n>-S<m> <变体执行者>`；不适用写 none>

<!-- 每步一行。截图放 package 的 evidence 目录，路径写成 package 内相对路径，同时是该步 evidence 的 artifact。截图拍到通过标准依赖的可见元素：标签、来源、数值、状态。观察结果写看到了什么，不写判断。“方法”列填 `走查` 或 `Playwright（原因）`，原因是 Spec 点名的测量或浏览器工具做不到的具体点。Spec 该步“承接”不是 `—` 时，inputRef 等于上一步的 outputRef。执行者变体不是主路径时，本记录只作走查证据，不登记 evidence（截图也不作 evidence artifact），runId 与主路径分开。 -->

| step id | 角色 | 入口 | 操作 | 方法 | 截图路径 | 观察结果 | inputRef / outputRef | 结论 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

## 须 Owner 本人验

只有三类：专业税务/会计判断；主观视觉与文案；不可逆外部副作用。命中的步骤在上表写“待 Owner”，并附入口、最短路径、测试身份和读回方法；其余步骤由验收者走查，不转交 Owner。
