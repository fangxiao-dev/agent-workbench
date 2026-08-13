---
name: plugin-lifecycle
description: Manage local plugin validation, cache refresh, reinstall, and host-native upgrades for Codex, Claude, and Grok.
disable-model-invocation: true
---

# plugin-lifecycle

显式调用此 Skill 管理插件生命周期。它会调用同目录的
`scripts/plugin_lifecycle.py`，不把宿主命令交给 agent 自行拼接。

## 流程

1. 准备一个外部 JSON config；不要把机器专属路径写回仓库。
2. 先运行 `validate`，确认插件名、source、manifest 和版本一致。
3. 对 `refresh`、`reinstall` 或 `upgrade` 先运行 dry-run，检查脚本输出的命令。
4. 只有用户明确要求执行时才加 `--apply`；脚本默认不会修改用户级 host 状态。
5. 读取 stdout 的单个 JSON envelope。任一 host 失败都报告 partial failure，不宣称整体成功。

## 调用

```powershell
python skills/plugin-lifecycle/scripts/plugin_lifecycle.py `
  --config <config.json> `
  --action validate|refresh|reinstall|upgrade `
  [--host codex claude grok] `
  [--apply]
```

省略 `--host` 时处理 config 中 `enabled: true` 的 host。路径支持 `~` 和环境变量展开。
版本只校验，不由脚本修改 manifest 或 marketplace。

## 边界

- `refresh`/`upgrade` 使用宿主原生命令；`reinstall` 才执行卸载再安装。
- Grok 使用 config 中的本地 `source`，不接受远程 marketplace。
- 脚本使用 `shell=False`，host 内一个步骤失败会停止该 host，但会继续汇总其他 host。
- 不能把 `planned` 当作执行成功；必须看到 `--apply` 的 `done` 和 `ok: true`。

配置字段和宿主命令映射见 [config.example.json](references/config.example.json)。
