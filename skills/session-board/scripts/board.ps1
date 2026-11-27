param(
    [ValidateSet('start', 'stop', 'restart', 'status')]
    [string]$Action = 'status',
    [int]$Port = 43188,
    [string]$Db,
    [string]$Model = 'deepseek-v4-flash',
    [string]$Script,
    [string]$AllowOrigin,
    [switch]$NoSummary
)

$ErrorActionPreference = 'Stop'
# PowerShell 5.1 has no $IsWindows; the whole 5.x line is Windows-only anyway.
$IsWin = if ($PSVersionTable.PSVersion.Major -ge 6) { $IsWindows } else { $true }

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..\..')
if (-not $Script) { $Script = Join-Path $repoRoot 'scripts/session_board.py' }
$Script = [System.IO.Path]::GetFullPath($Script)
if (-not $Db) {
    $Db = if ($IsWin) { 'D:\vibe-code-life\SessionBoard\board.sqlite3' }
          else { Join-Path $HOME 'SessionBoard/board.sqlite3' }
}
$logDir = Split-Path -Parent $Db
$log = Join-Path $logDir 'server.log'
$errLog = Join-Path $logDir 'server.err.log'

function Get-Python {
    foreach ($name in @('python', 'python3')) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) { return $cmd.Source }
    }
    throw '找不到 python / python3，请先加入 PATH'
}

function Get-BoardProcess {
    if ($IsWin) {
        Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
            Where-Object { $_.CommandLine -and ($_.CommandLine -like '*session_board.py*' -or $_.CommandLine -like '*scripts.session_board*') } |
            Select-Object ProcessId, CommandLine
    } else {
        foreach ($line in (& ps -axo pid=,command=)) {
            if ($line -match 'session_board\.py|scripts\.session_board') {
                $pidText, $cmd = $line.Trim() -split '\s+', 2
                [pscustomobject]@{ ProcessId = [int]$pidText; CommandLine = $cmd }
            }
        }
    }
}

function Get-Health {
    try {
        $response = Invoke-WebRequest "http://127.0.0.1:$Port/" -UseBasicParsing -TimeoutSec 3
        return $response.StatusCode
    } catch {
        return 0
    }
}

function Stop-Board {
    $running = @(Get-BoardProcess)
    if (-not $running) { Write-Output '看板没有在运行'; return }
    foreach ($proc in $running) { Stop-Process -Id $proc.ProcessId -Force }
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Milliseconds 200
        if (-not @(Get-BoardProcess)) { break }
    }
    Write-Output ("已停止看板进程 " + (($running | ForEach-Object { $_.ProcessId }) -join ', '))
}

function Get-Args {
    # -m from the module root: the board imports its siblings as `scripts.*`, which only resolves
    # when the checkout root is on sys.path.
    $arguments = @('-m', 'scripts.session_board', '--db', $Db, '--port', "$Port")
    if ($AllowOrigin) { $arguments += @('--allow-origin', $AllowOrigin) }
    if (-not $NoSummary) { $arguments += @('--deepseek-model', $Model) }
    return $arguments
}

function Start-Board {
    if (-not (Test-Path -LiteralPath $Script)) {
        throw "找不到 $Script（当前工作区可能不在有看板代码的分支上，切回 main 或传 -Script）"
    }
    if (@(Get-BoardProcess)) { Write-Output '看板已在运行，需要换参数请先 -Action stop'; return }
    if (Get-Health) { throw "端口 $Port 已被别的程序占用" }
    if (-not (Test-Path -LiteralPath $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
    $startArgs = @{
        FilePath               = Get-Python
        ArgumentList           = Get-Args
        WorkingDirectory       = Split-Path -Parent (Split-Path -Parent $Script)
        RedirectStandardOutput = $log
        RedirectStandardError  = $errLog
    }
    if ($IsWin) { $startArgs.WindowStyle = 'Hidden' }
    Start-Process @startArgs | Out-Null
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Milliseconds 250
        if (Get-Health) {
            Write-Output "看板已启动：http://127.0.0.1:$Port"
            Write-Output "日志：$log"
            return
        }
        if (-not @(Get-BoardProcess)) { break }
    }
    $tail = if (Test-Path -LiteralPath $errLog) { Get-Content -LiteralPath $errLog -Tail 5 } else { @() }
    throw ("启动失败，检查 $errLog`n" + ($tail -join "`n"))
}

switch ($Action) {
    'stop' { Stop-Board }
    'start' { Start-Board }
    'restart' { Stop-Board; Start-Board }
    'status' {
        $running = @(Get-BoardProcess)
        $code = Get-Health
        if ($running) { Write-Output ("进程：" + (($running | ForEach-Object { $_.ProcessId }) -join ', ')) }
        else { Write-Output '进程：无' }
        Write-Output "HTTP：$(if ($code) { "$code http://127.0.0.1:$Port" } else { '无响应' })"
        if ($running -and -not $code) { Write-Output '进程在但页面不通：确认启动时的工作区还有 scripts/session_board.html，然后 restart' }
    }
}
