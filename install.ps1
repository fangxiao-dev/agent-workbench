#Requires -Version 5.1
# 注意：创建目录软链接需要 Windows 开发者模式 或 以管理员身份运行。
# 开启开发者模式：设置 → 系统 → 开发者选项 → 开发者模式
$ErrorActionPreference = "Stop"

$WorkbenchDir = $PSScriptRoot
$Target = if ($args[0]) { $args[0] } else { (Get-Location).Path }
$Target = (Resolve-Path $Target).Path
$ClaudeHome = Join-Path $env:USERPROFILE ".claude"

Write-Host "🔧 Workbench: $WorkbenchDir"
Write-Host "📁 Target project: $Target"
Write-Host ""

# Helper: 创建软链接，先清除同名旧链接或目录
function Set-Symlink($src, $dst) {
    if (Test-Path $dst) { Remove-Item -Force -Recurse $dst }
    $isDir = (Get-Item $src) -is [System.IO.DirectoryInfo]
    New-Item -ItemType SymbolicLink -Path $dst -Target $src | Out-Null
}

# ── 1. Skills → ~/.claude/skills/ (symlinks) ─────────────────────
Write-Host "🔗 链接 skills 到 $ClaudeHome\skills\"
New-Item -ItemType Directory -Force -Path (Join-Path $ClaudeHome "skills") | Out-Null
Get-ChildItem -Path (Join-Path $WorkbenchDir "skills") -Directory | ForEach-Object {
    $dst = Join-Path $ClaudeHome "skills\$($_.Name)"
    Set-Symlink $_.FullName $dst
    Write-Host "  ✅ $($_.Name)"
}

# ── 2. Agents → ~/.claude/agents/ (symlinks) ─────────────────────
Write-Host ""
Write-Host "🔗 链接 agents 到 $ClaudeHome\agents\"
New-Item -ItemType Directory -Force -Path (Join-Path $ClaudeHome "agents") | Out-Null
Get-ChildItem -Path (Join-Path $WorkbenchDir "agents") -Directory | ForEach-Object {
    $dst = Join-Path $ClaudeHome "agents\$($_.Name)"
    Set-Symlink $_.FullName $dst
    Write-Host "  ✅ $($_.Name)"
}

# ── 3. Commands → ~/.claude/commands/ (symlinks) ──────────────────
Write-Host ""
Write-Host "🔗 链接 commands 到 $ClaudeHome\commands\"
New-Item -ItemType Directory -Force -Path (Join-Path $ClaudeHome "commands") | Out-Null
Get-ChildItem -Path (Join-Path $WorkbenchDir "commands") -File | ForEach-Object {
    $dst = Join-Path $ClaudeHome "commands\$($_.Name)"
    Set-Symlink $_.FullName $dst
    Write-Host "  ✅ $($_.Name)"
}

# ── 4. CLAUDE.md（不覆盖已有的）─────────────────────────────────
Write-Host ""
$claudeMd = Join-Path $Target "CLAUDE.md"
if (-not (Test-Path $claudeMd)) {
    $projectName = Split-Path $Target -Leaf
    $tpl = Get-Content (Join-Path $WorkbenchDir "templates\CLAUDE.md.tpl") -Raw
    ($tpl -replace '\{\{PROJECT_NAME\}\}', $projectName) | Set-Content -Path $claudeMd -Encoding UTF8
    Write-Host "📝 CLAUDE.md 已生成（来自模板）"
} else {
    Write-Host "⏭️  CLAUDE.md 已存在，跳过（运行 /audit 检查质量）"
}

# ── 5. .gitignore 补丁 ───────────────────────────────────────────
$gitignore = Join-Path $Target ".gitignore"
if (-not (Test-Path $gitignore)) {
    New-Item -ItemType File -Force -Path $gitignore | Out-Null
}
$content = Get-Content $gitignore -Raw -ErrorAction SilentlyContinue
if (-not ($content | Select-String -Pattern '\.claude/settings\.local\.json' -Quiet)) {
    Add-Content -Path $gitignore -Value ".claude/settings.local.json"
    Write-Host "📝 .gitignore 已更新"
}

Write-Host ""
Write-Host "✅ 完成。在任意项目的 Claude Code 里运行 /audit 开始检查。"
