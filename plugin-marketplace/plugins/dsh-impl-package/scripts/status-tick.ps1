# status-tick.ps1 — Impl-Package 工作流的一次性状态取样器
#
# 用途：给长驻 worker（subagent_codex 等一发式派发，无中途输出）提供周期可见性。
# 本脚本只取样并输出当前状态，不做心跳、看门狗或自动 kill（与
# subagent-driven-development/progress-file 模板的轻量设计一致）。
#
# 链式播报模式（主 session 驱动）：
#   1) 主 session 以 run_in_background 启动一次本脚本（间隔由调用方 sleep）；
#   2) job 结束后宿主通知主 session；
#   3) 主 session 转播输出行，并以新 job 重新武装下一次取样。
#
# 输出格式（稳定，供主 session 原样转播）：
#   [HH:mm:ss] env: api=<ok|restarting|down> web=<status> tax=<status>
#   [HH:mm:ss] git: commits=+<N> head=<short> worktree=<git diff --shortstat>
#   [HH:mm:ss] <unit>: <progress-file 最后一行>        # 每 unit 一行
#   [HH:mm:ss] hints: <PathHints 命中的阶段标签>        # 仅当 -PathHints 提供
#
# 参数：
#   -WorkDir        工作根（默认当前目录；git 命令在此时执行）
#   -PackageDir     仓库相对 package 路径（可选；提供后读取
#                   <PackageDir>/.impl-package/progress/*.md 的尾部行）
#   -BaselineCommit git 基线 commit（可选；提供后输出 commits=+N）
#   -PathHints      有序阶段推导表（可选）：@{ "<路径正则>" = "<阶段标签>" }
#                   对 git status 的脏路径逐条匹配，命中即输出标签。
#   -TimeoutSec     健康检查超时秒数（默认 4）
#
# 示例（KEX-01A 会话）：
#   & <plugin>/scripts/status-tick.ps1 -WorkDir <repo> `
#       -PackageDir docs/domains/finance-assistant/implementations/2026-08-23-mvp-kontierung-extf-hardening `
#       -BaselineCommit afbcae79760b09cade43acf970f57270f87e7bea `
#       -PathHints @{ 'schema\.prisma'='schema'; 'review-sachkonto-selection'='sidecar-module';
#                     'review-workspace\.dto'='dto'; 'review-workspace\.service'='service';
#                     'formal-kontierung-workbench'='override-block' }
param(
  [string]$WorkDir = (Get-Location).Path,
  [string]$PackageDir = "",
  [string]$BaselineCommit = "",
  [hashtable]$PathHints = @{},
  [int]$TimeoutSec = 4
)

Set-Location $WorkDir
$ts = Get-Date -Format "HH:mm:ss"

# ---- env：KaiSpan local-dev 契约端点（docs/agents/local-development.md）----
$live = "down"
try { $r = Invoke-RestMethod "http://127.0.0.1:4000/api/health/live" -TimeoutSec $TimeoutSec; if ($r.status -eq "ok") { $live = "ok" } } catch {}
$ready = "down"
try { $r2 = Invoke-RestMethod "http://127.0.0.1:4000/api/health/ready" -TimeoutSec $TimeoutSec; if ($r2.status -eq "ok") { $ready = "ok" } } catch {}
$api = if ($ready -eq "ok") { "ok" } elseif ($live -eq "ok") { "restarting" } else { "down" }
$web = "down"
try { $w = Invoke-WebRequest "http://127.0.0.1:3000" -TimeoutSec $TimeoutSec -UseBasicParsing; $web = $w.StatusCode } catch {}
$tax = "down"
try { $t = Invoke-WebRequest "http://127.0.0.1:3001" -TimeoutSec $TimeoutSec -UseBasicParsing; $tax = $t.StatusCode } catch {}

# ---- git：commits/head/worktree 改动量 ----
$cnt = ""
$head = ""
$stat = ""
if (Test-Path ".git") {
  if ($BaselineCommit -ne "") {
    $cnt = (git rev-list --count "$BaselineCommit..HEAD" 2>$null)
    if ($null -eq $cnt) { $cnt = "" }
  }
  $head = (git log --oneline -1 2>$null)
  $stat = ((git diff --shortstat HEAD 2>$null) -join "")
}

# ---- progress 文件：每 unit 一行（尾部行） ----
$progressLines = @()
if ($PackageDir -ne "") {
  $progressDir = Join-Path $PackageDir ".impl-package\progress"
  if (Test-Path $progressDir) {
    Get-ChildItem $progressDir -Filter *.md -ErrorAction SilentlyContinue | ForEach-Object {
      $last = Get-Content $_.FullName -Tail 1 -ErrorAction SilentlyContinue
      if ($last) { $progressLines += "[$ts] $($_.BaseName): $last" }
    }
  }
}

# ---- PathHints：脏路径 → 阶段标签 ----
$hintLabels = @()
if ($PathHints.Count -gt 0) {
  $paths = git status --porcelain 2>$null | ForEach-Object { $_.Substring(3) }
  foreach ($entry in $PathHints.GetEnumerator()) {
    foreach ($p in $paths) {
      if ($p -match $entry.Key) { $hintLabels += $entry.Value; break }
    }
  }
}

Write-Output "[$ts] env: api=$api web=$web tax=$tax"
if ($head) {
  $commitPart = if ($cnt -ne "") { "commits=+$cnt " } else { "" }
  $statPart = if ($stat) { " worktree=$stat" } else { "" }
  Write-Output "[$ts] git: ${commitPart}head=$head$statPart"
}
$progressLines | ForEach-Object { Write-Output $_ }
if ($hintLabels.Count -gt 0) {
  Write-Output "[$ts] hints: $($hintLabels -join '/')"
}
