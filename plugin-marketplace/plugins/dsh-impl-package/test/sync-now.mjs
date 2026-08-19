import { mkdirSync } from 'node:fs'
import { syncPresetTrees, bundledPresetsRoot, resolveDshHome } from '../lib/index.mjs'

const target = `${resolveDshHome()}/.agent-presets`
mkdirSync(target, { recursive: true })
const result = syncPresetTrees(bundledPresetsRoot(), target)
console.log('target:', target)
console.log('synced:', JSON.stringify(result.synced))
console.log('failed:', JSON.stringify(result.failed))
