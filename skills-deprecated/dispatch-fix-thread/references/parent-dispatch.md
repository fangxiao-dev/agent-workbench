# Parent: dispatch (Deprecated)

只处理 parent 的首次派发。目标是建立可靠边界并释放 parent 容量，不代替 fixer 管理修复过程。

## 适用门槛

review 去重后，默认至少有四个已确认且需要修改业务代码的 bugs 才派发。以下工作留在 parent：

- 三个以内的 P2 小 bug；
- 只修改文档、证据或进度记录；
- 单个可快速完成的局部修复；
- 尚未确认、仍需调查或裁决的 findings。

少量 P1 或高风险 bugs 不自动派发；Owner 显式调用可以覆盖数量门槛。若本次调用不满足默认门槛且没有显式覆盖，说明原因并留在 parent。

## 派发合同

先读取仓库 instructions，并使用 `$git-workflow` 确认 Git 边界。派发前解析并固定：

- repository root、parent task id、parent branch；
- immutable `reviewed_head`；
- 每个 finding 的稳定 ID、摘要和 acceptance points；
- 权威 findings 来源（若有）；
- fixer 可写范围与明确排除项；
- fixer 承担的 focused verification；
- parent 保留的 remaining verification；
- 禁止的本地、远程和外部副作用。

`reviewed_head` 必须解析为 commit。检查 parent dirty state 并把它视为保护边界；fixer 从该 commit 开始，不携带 parent 未提交内容。

生成唯一 `fix_id` 和 `%TEMP%\dispatch-fix-thread\<fix-id>\`。为本次修复只分配一套 fixer branch/worktree，并确保它从 `reviewed_head` 开始。使用 [`../scripts/bookkeeping.py`](../scripts/bookkeeping.py) 把实际 branch、worktree 和 expected HEAD 写入 immutable request；finding 内容必须写入 request，不能只引用以后可能变化的路径。脚本的 `--help` 是命令接口权威。

用宿主原生能力创建一个绑定该隔离 worktree 的正常 fixer task。若宿主在创建 task 时才分配 worktree，首次 prompt 只做 anchor 核验；待宿主返回实际 branch/worktree 后再创建 request。无论宿主采用哪种顺序，都只保留一套实际 fixer branch/worktree。任一步失败时保留已存在内容供重试，不并行创建第二套。

首次消息只要求 fixer 核验 repository、worktree、branch 和 expected HEAD，并返回 anchor receipt。anchor 未确认时不发送 findings 或修复正文。确认后再发送 continuation，至少包含：

```text
使用 $dispatch-fix-thread
role=fixer
action=run
records=<absolute records directory>
parent_task=<task id>
从 request.json 和 Git anchors 开始；不要依赖 parent 私有上下文。
```

task 已创建但 anchor receipt 缺失或不一致时，派发尚未完成；保存现有事实并报告，不猜测 task 已经接管。

## 等待边界

anchor 确认后结束主动协调。parent 不启动 poll loop，不读取 worker 状态，也不指导 fixer 分组或返工。之后只有 fixer 的 `ready|blocked` 消息、Owner 主动询问，或 parent 被其他事件唤醒时，才按需读取 bookkeeping。

`updated_at` 只能在读取时辅助识别疑似停滞，不是 heartbeat，也不授权自动接管。

## 完成条件

派发完成时，parent 能报告且保存以下六项：`fix_id`、records 绝对路径、fixer task id、fixer branch、fixer worktree、与 `reviewed_head` 一致的 anchor receipt。缺少任一项都只能报告 dispatch incomplete。
