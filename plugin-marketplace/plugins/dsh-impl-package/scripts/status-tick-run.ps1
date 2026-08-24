# status-tick-run.ps1 — status-tick 的有界运行包装（看门狗 + 日志落盘）
#
# 链式播报的可靠性包装：sleep 间隔 → 在带超时的子 job 中运行 status-tick.ps1
# （30s 硬上限，防止健康检查偶发挂起卡死整条链）→ 输出同时追加到日志文件。
#
# 参数：
#   -IntervalSec  两次取样间隔（默认 180）
#   -TickScript    status-tick.ps1 路径（默认取本脚本同目录）
#   -LogFile       输出追加日志（默认 %TEMP%\kaispan-status.log）
#   其余参数原样透传给 status-tick.ps1（-WorkDir/-PackageDir/-BaselineCommit/-PathHints/-TimeoutSec）
#
# 主 session 以 run_in_background 启动；job 结束后宿主通知主 session，
# 主 session 转播输出并重新武装下一次。

param(
  [int]$IntervalSec = 180,
  [string]$TickScript = "",
  [string]$LogFile = "",
  [string]$WorkDir = (Get-Location).Path,
  [string]$PackageDir = "",
  [string]$BaselineCommit = "",
  [hashtable]$PathHints = @{},
  [int]$TimeoutSec = 4
)

if ($TickScript -eq "") { $TickScript = Join-Path $PSScriptRoot "status-tick.ps1" }
if ($LogFile -eq "") { $LogFile = Join-Path $env:TEMP "kaispan-status.log" }

Start-Sleep -Seconds $IntervalSec

$job = Start-Job -ScriptBlock {
  param($script, $wd, $pkg, $base, $hints, $tmo)
  & $script -WorkDir $wd -PackageDir $pkg -BaselineCommit $base -PathHints $hints -TimeoutSec $tmo
} -ArgumentList $TickScript, $WorkDir, $PackageDir, $BaselineCommit, $PathHints, $TimeoutSec

$result = Wait-Job -Job $job -Timeout 30
if ($null -eq $result) {
  Stop-Job -Job $job -ErrorAction SilentlyContinue
  Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
  Write-Output "[status-tick-run] tick timed out after 30s"
  Add-Content -Path $LogFile -Value "[status-tick-run] tick timed out after 30s"
  exit 1
}

$lines = Receive-Job -Job $job
Remove-Job -Job $job -Force
foreach ($line in $lines) {
  Write-Output $line
  Add-Content -Path $LogFile -Value $line
}
exit 0
