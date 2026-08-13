# Worker Resolver

本页是统一入口的解析和恢复合同，不是新的运行时 registry。解析事实来自 active Skill catalog、宿主 agent profile 或调用者明确提供的 model/prompt。

## 解析表

| 引用 | 解析事实 | 启动约束 |
| --- | --- | --- |
| `$grok-worker` | 仓库 `skills/call-grok/SKILL.md` 及其 `scripts/grok_task.py` | 只传 bounded brief、cwd、权限和必要资源；不传 model/effort |
| `@luna-worker` | 宿主现有的 `luna-worker` agent profile | fresh invocation；不得改用户级配置 |
| `<model>/<effort>` | 当前宿主支持的直接 profile | caller 必须显式授权该 override |
| `prompt:<slug>` | 当前宿主可读取的 prompt profile | profile 不存在或不唯一则 BLOCKED |
| `main-session` | 当前主 session | 仅 local，必须给出 reason |

解析步骤：验证引用格式 → 验证唯一实体和宿主能力 → 组装 canonical brief → 记录实际 worker → 启动 fresh invocation。任何一步不能确定都返回 `Outcome: BLOCKED`。

## 统一 envelope

```yaml
status: DONE | BLOCKED | INCOMPLETE
mode: investigate | implement | fix | verify
worker: <resolved logical reference>
source_unit: <stable bounded-unit id>
summary: <short result>
evidence: []
artifacts: []
blocker: null | <reason>
fallback_from: null | <logical reference>
session_id: null | <executor session id>
review_state: NOT_REQUIRED | PENDING_REVIEW | PASSED | FINDING | BLOCKED
```

`status` 只描述 worker 执行；`review_state` 描述结果能否交给主 session。`PENDING_REVIEW` 必须保留上述 envelope、comparison point 和待审 reviewer brief，写入当前 Attempt ER；只有旧 3.4 Task package 才可追加到 legacy Task Handoff。恢复时不得把它解释为 DONE。

## 一次 fallback

只对默认 `$grok-worker` 的 `INCOMPLETE` 进入本流程：

1. 确认 executor 已退出或被清理；状态未知直接 `BLOCKED`。
2. 检查授权写集内 diff、临时文件和外部 residue；来源不明或越界直接 `BLOCKED`。
3. 用同一 canonical brief 启动一次 fresh `@luna-worker`，携带 terminal status、cleanup、residue 和 `fallback_from: "$grok-worker"`。
4. fallback 的 `DONE` 继续按原 `review` 规则处理；fallback 的 `BLOCKED` 或 `INCOMPLETE` 不再重试，统一返回 `BLOCKED`。

显式指定的其他 worker 没有隐式 fallback；只有其自身 Skill 合同明确授权时才能恢复。业务 `BLOCKED` 永远不上述恢复路径。
