/**
 * dsh-dispatch-scan — host half.
 *
 * Runs inside the DSH host process when the profile bundle is mounted:
 *   1. patches the target agent preset in ~/.dsh/.agent-presets/<preset>/
 *      by copying `scan-hook.mjs` next to it and appending the
 *      `dispatch-scan-hook` row to `agent.cordis.yml` — idempotently, on
 *      every startup, so preset re-syncs by other plugins cannot lose the
 *      patch (it is re-applied at the next launch);
 *   2. announces the patch through a system-prompt section.
 *
 * The heavy lifting lives in the preset-local hook (presets/patch/scan-hook.mjs).
 * Dependency-free by design: only node: builtins.
 */

import { existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { homedir } from 'node:os'

export const name = 'dsh-dispatch-scan'
export const inject = ['systemPrompt']

/** Absolute path of the bundled hook file inside this package. */
export function bundledHookFile() {
  return fileURLToPath(new URL('../presets/patch/scan-hook.mjs', import.meta.url))
}

/** Resolve the DSH home directory (~/.dsh unless DSH_HOME overrides). */
export function resolveDshHome(env = process.env, home = homedir()) {
  const raw = env.DSH_HOME
  if (raw !== undefined && raw.trim() !== '') {
    const value = raw.trim()
    return value.startsWith('~/') ? join(home, value.slice(2)) : value
  }
  return join(home, '.dsh')
}

export const DEFAULT_CONFIG = {
  presetName: 'impl-package',
  hookId: 'dispatch-scan-hook',
}

const HOOK_ROW_BLOCK = (hookId) =>
  [
    '',
    '# ── dispatch-scan: per-step parallel-dispatch checklist (patched by dsh-dispatch-scan) ──',
    `- id: ${hookId}`,
    '  name: ./scan-hook.mjs',
    '',
  ].join('\n')

/** Whether the preset's agent.cordis.yml already carries the hook row. */
export function hasHookRow(cordisText, hookId) {
  return new RegExp(`^\\s*-\\s+id:\\s*${hookId}\\s*$`, 'm').test(String(cordisText ?? ''))
}

/** Sidecar stamp file written by other plugins' preset sync (e.g.
 *  dsh-impl-package) into a synced preset tree. */
const STAMP_FILE = '.dsh-sync-stamp'

/**
 * Patch one agent preset: ensure scan-hook.mjs is present next to
 * `agent.cordis.yml` and the hook row exists in it, then preserve the preset
 * sync stamp written by the preset-owning plugin — otherwise that plugin's
 * next sync sees a changed tree and wipes the patch. Returns
 * { presetDir, hookFile, patched: 'added' | 'present' | 'missing', stampPreserved }.
 */
export function patchPreset(presetDir, hookFile, hookId = DEFAULT_CONFIG.hookId) {
  if (!existsSync(presetDir)) {
    return { presetDir, hookFile, patched: 'missing', stampPreserved: false }
  }
  const cordisPath = join(presetDir, 'agent.cordis.yml')
  if (!existsSync(cordisPath)) {
    return { presetDir, hookFile, patched: 'missing', stampPreserved: false }
  }
  // Inherit the owning plugin's sync stamp BEFORE touching the tree: the
  // stamp encodes the pristine source tree, and after our patch the tree
  // intentionally differs from it — restoring the same stamp makes the next
  // sync compare equal and skip the destructive re-copy. If the owning
  // plugin upgrades, its source stamp changes, the re-copy wipes the patch,
  // and the next launch of this plugin re-applies it.
  const stampPath = join(presetDir, STAMP_FILE)
  let stamp = undefined
  try {
    stamp = readFileSync(stampPath, 'utf-8')
  } catch {
    stamp = undefined
  }

  mkdirSync(presetDir, { recursive: true })
  writeFileSync(join(presetDir, 'scan-hook.mjs'), readFileSync(hookFile))

  const current = readFileSync(cordisPath, 'utf8')
  let patched = 'present'
  if (!hasHookRow(current, hookId)) {
    writeFileSync(cordisPath, `${current.replace(/\s+$/, '')}${HOOK_ROW_BLOCK(hookId)}`)
    patched = 'added'
  }
  if (stamp !== undefined) {
    writeFileSync(stampPath, stamp)
  }
  return { presetDir, hookFile, patched, stampPreserved: stamp !== undefined }
}

/**
 * Patch the default target preset (or `config.presetName`) inside the
 * harness-home agent-presets root. Called on every startup.
 */
export function applyPatches(config = {}) {
  const presetName = String(config.presetName || DEFAULT_CONFIG.presetName)
  const dshHome = resolveDshHome()
  const presetDir = join(dshHome, '.agent-presets', presetName)
  const results = [patchPreset(presetDir, bundledHookFile(), String(config.hookId || DEFAULT_CONFIG.hookId))]
  return results.map((result) => ({ ...result, presetName }))
}

export function apply(ctx, config = {}) {
  const results = applyPatches(config)
  for (const result of results) {
    ctx.logger?.info?.(
      `dsh-dispatch-scan: preset "${result.presetName}" patch=${result.patched} stampPreserved=${result.stampPreserved} (${result.presetDir})`
    )
  }
}

// Bare-import entry (e.g. `node lib/index.mjs --apply` for manual runs).
if (process.argv[1] !== undefined) {
  const entry = `file:///${process.argv[1].replace(/\\/g, '/')}`
  if (import.meta.url === entry) {
    const results = applyPatches()
    for (const result of results) {
      console.log(`preset=${result.presetName} patch=${result.patched} dir=${result.presetDir}`)
    }
  }
}
