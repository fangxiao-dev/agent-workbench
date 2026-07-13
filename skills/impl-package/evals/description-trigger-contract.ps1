$ErrorActionPreference = 'Stop'

$implRoot = Split-Path -Parent $PSScriptRoot
$members = Get-ChildItem -LiteralPath $implRoot -Recurse -Filter SKILL.md -File | Where-Object { $_.DirectoryName -ne $implRoot }

if ($members.Count -lt 8) {
    throw "Expected Impl-Package member skills, found only $($members.Count)."
}

foreach ($member in $members) {
    $text = Get-Content -LiteralPath $member.FullName -Raw
    if ($text -notmatch '(?s)^---\r?\n.*?\r?\n---') {
        throw "Missing YAML frontmatter: $($member.FullName)"
    }
    $frontmatter = $matches[0]
    if ($frontmatter.Contains('Impl-Package 体系的')) {
        throw "Member description must lead with capability and trigger conditions, not the suite name: $($member.FullName)"
    }
    if ($frontmatter -notmatch '(?m)^description:\s*(>|\S)') {
        throw "Missing description: $($member.FullName)"
    }
}

$router = Get-Content -LiteralPath (Join-Path $implRoot 'SKILL.md') -Raw
if (-not $router.Contains('Impl-Package 体系的入口地图与路由')) {
    throw 'The impl-package router may retain the suite name because routing the suite is its standalone capability.'
}

Write-Output 'Impl-Package member descriptions are independently triggerable.'
