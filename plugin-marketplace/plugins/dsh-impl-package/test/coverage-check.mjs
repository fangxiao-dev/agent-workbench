import { readFileSync } from 'node:fs'

const t = readFileSync('D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/impl-package/skills/dev-with-track/situations.yaml', 'utf-8')
const slugs = [...t.matchAll(/^\s*- slug:\s*([^\s]+)\s*$/gm)].map((m) => m[1])
console.log('slugs in situations.yaml:', slugs.length)
const p = JSON.parse(readFileSync('D:/CodeSpace/agent-workbench/plugin-marketplace/plugins/dsh-impl-package/presets/impl-package/protocols.json', 'utf-8'))
const uncovered = slugs.filter((s) => p[s] === undefined)
console.log('covered explicitly:', slugs.length - uncovered.length)
console.log('uncovered (use default):', uncovered.length, uncovered.join(', '))
