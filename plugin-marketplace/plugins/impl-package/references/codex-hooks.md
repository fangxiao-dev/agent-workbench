# Codex Hooks

Codex manifest 加载 `hooks/codex-hooks.json`，提供两项可选的宿主能力。新建或变更后的 Hook 必须先由用户信任；未信任、禁用或执行失败时，Skills 仍按各自 reference fallback 工作。

## H1 · State guard

`PreToolUse(apply_patch)` 只阻止直接 Add/Update/Delete/Move 真实 package 的 `.impl-package/state.json`，并提示使用 `scripts/impl_package_state.py`。`tests/fixtures/**` 不属于 live package；Bash、Progress、Gate 和其它写入路径不在这个 guard 的覆盖声明内。

## H2 · Resume Capsule

普通 SDD 不会自动获得 package context。只有 Codex 在 `dev-with-track` 确认 package anchor 后执行：

```text
python <plugin-root>/hooks/impl_package_hooks.py activate --package <package>
```

绑定按 Codex session 与 Git worktree 隔离，保存在 worktree 本地 Git metadata，不进入仓库或 package artifact。绑定后，`SessionStart(startup|resume|compact)` 使用只读 situation render 注入 `Impl-Package Resume Capsule v1`；Capsule 是导航事实，不是 Evidence、Acceptance、Gate、closure 或 dispatch credential。

显式离开 package 工作时执行：

```text
python <plugin-root>/hooks/impl_package_hooks.py deactivate
```

同 session 未解绑就切换到普通任务时，后续 resume/compact 仍会注入 Capsule。首次恢复 Capsule 缺失/失配或发生未知外部状态变化时，按 `dev-with-track/references/runtime-protocol.md` 完整恢复。
