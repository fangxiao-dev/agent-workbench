# Codex Hooks

Codex manifest 加载 `hooks/codex-hooks.json`，提供两项可选的宿主能力。新建或变更后的 Hook 必须先由用户信任；未信任、禁用或执行失败时，Skills 仍按各自 reference fallback 工作。

## H1 · State guard

`PreToolUse(apply_patch)` 只阻止直接 Add/Update/Delete/Move 真实 package 的 `.impl-package/state.json`，并提示使用 `scripts/impl_package_state.py`。`tests/fixtures/**` 不属于 live package；Bash、Progress、Gate 和其它写入路径不在这个 guard 的覆盖声明内。

## H2 · Resume Capsule

普通 Dispatcher 调用不会自动获得 package context。只有 Codex 在 `dev-with-track` 确认 package anchor 后执行：

```text
python <plugin-root>/hooks/impl_package_hooks.py activate --package <package>
```

绑定按 Codex session 与 Git worktree 隔离，保存在 worktree 本地 Git metadata，不进入仓库或 package artifact。绑定后，`SessionStart(startup|resume|compact)` 使用只读 situation render 注入 `Impl-Package Resume Capsule v1`；Capsule 是导航事实，不是 Evidence、Acceptance、Gate、closure 或 dispatch credential。

Capsule 展示 blocking、runnable、withheld 与 in_flight。投影只包含 renderer 派生的业务动作，不保证覆盖主控可发现的全部工作；主控仍按当前 dependency、授权、资源与 in-flight 判断。完整内容超过宿主预算时，改为明确标记 `projection-complete: false` 的计数摘要与完整只读投影入口，保持整个恢复提示在预算内。

显式离开 package 工作时执行：

```text
python <plugin-root>/hooks/impl_package_hooks.py deactivate
```

同 session 未解绑就切换到普通任务时，后续 resume/compact 仍会注入 Capsule。Capsule 缺失、失配、state 已变化或 `projection-complete: false` 时，读取 [Runtime Protocol](../skills/dev-with-track/references/runtime-protocol.md) 完成恢复。

## ZCode 差异

ZCode manifest（`.zcode-plugin/plugin.json`）加载 `hooks/zcode-hooks.json`，同一脚本提供等价的两项能力：

- State guard：`PreToolUse` matcher 为 `^(Edit|Write|ApplyPatch)$`（ZCode 工具名与别名），按 `tool_input.file_path` 判定，不再解析 apply_patch 补丁文本；deny 语义与 fixture 豁免与 Codex 一致。
- Resume Capsule：`SessionStart(startup|resume|compact)` 行为一致。ZCode 不向 agent 运行的命令暴露 session id，`activate`/`deactivate` 无 session 环境变量时自动使用仓库级 `default` 绑定（同仓库任意 session 可恢复 Capsule）；显式 session 绑定优先。
- 注册形态使用 `type: "process"`（参数向量、无 shell、跨平台）；ZCode 无 `additionalContextLimit` 字段，超预算回退由脚本内 1200 字节预算逻辑保证。
