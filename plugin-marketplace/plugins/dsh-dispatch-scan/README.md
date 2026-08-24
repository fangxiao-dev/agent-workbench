# dsh-dispatch-scan

让「等待即扫描」成为每轮强制习惯的 DSH 插件：`agent/pre-step` hook 在**每一步**前注入一条紧凑的并行派发清单，使主控 agent 在即将进入等待/轮询/阻塞时先扫描可并行派发项——不依赖模型记忆。

## 为什么需要 hook 而不是 skill

- SKILL.md 只在会话按需加载一次，管「协议」，管不了「每轮提醒」。
- pre-step hook 是 preset 级强制：每轮必现，跟着 preset 走，换机器/换会话不丢。
- 注入是无条件的（无 throttle、无状态），措辞做成条件式（「若本轮将进入等待…」），由 agent 自行过滤非等待轮，等于软条件、零噪音成本。

## 每轮注入的内容

```
[dispatch-scan] 若本轮将进入等待/轮询/阻塞，先扫可并行派发项：
  1. 已提交未 review 的 fix → 派只读 recheck
  2. 改动域回归（兄弟 spec / 集成层 / 与组件测试互补的 UI 冒烟）
  3. 零依赖落盘：progress / evidence / 文档
  4. 只读预研（后续 ticket investigations）或环境预热
  纪律：只读与写分离；后台任务带 liveness + kill 规则；派发前确认结果消费者
```

清单来源：KEX-01A 执行中反复被用户点出的「还有没有可以提前派发的」——沉淀为固定检查项。纪律条目来自该任务的实证教训（recheck 与 fix 并行时的文件冲突、codex 后台挂起需要 kill 规则、无效派发无人消费）。

## 安装与生效

1. 把本插件放入 plugin-marketplace（`plugins/dsh-dispatch-scan`），DSH 启动时 cordis patch 挂载 host 插件。
2. 插件启动时**幂等补丁**目标 preset（默认 `impl-package`，可用 `presetName` 配置改）：
   - 把 `scan-hook.mjs` 复制到 `~/.dsh/.agent-presets/<preset>/`
   - 在 `agent.cordis.yml` 末尾追加 `dispatch-scan-hook` 行（已存在则跳过）
3. 每次启动都会重新检查补丁——即使其他插件重同步 preset 覆盖了补丁，下次启动自动补回。

手动补丁（无需重启 DSH）：

```bash
node lib/index.mjs --apply
# 或带自定义 preset：
node -e "import('./lib/index.mjs').then(m => console.log(m.applyPatches({ presetName: 'my-preset' })))"
```

## 结构

```
plugins/dsh-dispatch-scan/
├── package.json          # dsh.bundle.patch → ./cordis.patch.yml
├── cordis.patch.yml      # insert host 插件行
├── presets/patch/
│   └── scan-hook.mjs     # pre-step hook（注入清单，跳过 delegated agents）
├── lib/index.mjs         # 启动幂等补丁 + 手动 --apply 入口
└── README.md
```

## 设计边界

- **不留痕**：hook 只提醒；扫描/派发决策与记录归主 session（trail 等现有机制）。
- **不污染子代理**：`delegationDepth >= 1`（review leaves / workers）跳过注入，其上下文保持 scoped。
- **判断归模型**：注入是导航，不是 gate。
