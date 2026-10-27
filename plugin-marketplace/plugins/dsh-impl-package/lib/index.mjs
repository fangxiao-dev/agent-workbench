/**
 * dsh-impl-package — host half.
 *
 * Runs inside the DSH host process when the profile bundle is mounted:
 *   1. syncs the bundled agent presets (presets/<name>/) into
 *      ~/.dsh/.agent-presets/<name>/ (the harness-home discovery root), so a
 *      new session can pick the preset from the selector;
 *   2. announces the adapter through a system-prompt section so the model
 *      knows the native situation injection and typed tools exist.
 *
 * The heavy lifting lives in the preset itself (situation-hook.mjs,
 * impl-tools.mjs) — this file only makes the preset discoverable.
 *
 * Dependency-free by design: only node: builtins. The preset sync follows the
 * dsh-liangshen pattern (MIT).
 */

import { existsSync, mkdirSync, readdirSync, readFileSync, realpathSync, rmSync, statSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { homedir } from 'node:os'

export const name = 'dsh-impl-package'
export const inject = ['systemPrompt']

/** Absolute path of the bundled preset tree inside this package. */
export function bundledPresetsRoot() {
  return fileURLToPath(new URL('../presets/', import.meta.url))
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

/** Structural sanity check for a bundled agent.cordis.yml (row opener + name). */
export function validateAgentCordis(text) {
  const errors = []
  const normalized = String(text ?? '').replace(/\r\n/g, '\n')
  if (normalized.trim() === '') return ['document is empty']
  const rows = [...normalized.matchAll(/^-\s+id:\s*(.*)$/gm)]
  for (const match of rows) {
    const id = match[1].trim()
    const lineNo = normalized.slice(0, match.index).split('\n').length
    if (id === '') errors.push(`line ${lineNo}: row has empty id`)
    const nameMatch = /^ {2}name:\s*(.+)$/m.exec(normalized.slice(match.index))
    if (nameMatch === null) {
      errors.push(`row "${id}": missing "name" key`)
    } else {
      const raw = nameMatch[1].trim()
      const unquoted = (raw.startsWith("'") && raw.endsWith("'")) || (raw.startsWith('"') && raw.endsWith('"'))
        ? raw.slice(1, -1)
        : raw
      if (!/^(\.\/|@|cordis:)/.test(unquoted)) {
        errors.push(`row "${id}": name "${unquoted}" must start with "./", "@" or "cordis:"`)
      }
    }
  }
  return errors
}

/** Sidecar stamp file written into a synced preset tree. */
const STAMP_FILE = '.dsh-sync-stamp'

/** Exact tree stamp: sorted map of relative file path → mtimeNs (BigInt as string). */
export function treeStamp(root) {
  const files = {}
  const walk = (dir, prefix) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const rel = prefix === '' ? entry.name : `${prefix}/${entry.name}`
      const abs = join(dir, entry.name)
      if (entry.isDirectory()) {
        walk(abs, rel)
      } else if (entry.name !== STAMP_FILE) {
        files[rel] = String(statSync(abs, { bigint: true }).mtimeNs)
      }
    }
  }
  walk(root, '')
  return JSON.stringify(Object.keys(files).sort().map((key) => [key, files[key]]))
}

function readStamp(target) {
  try {
    return readFileSync(join(target, STAMP_FILE), 'utf-8')
  } catch {
    return undefined
  }
}

/**
 * Sync preset trees from `sourceRoot` into `targetRoot` (the harness-home
 * agent-presets root). A preset is re-copied only when its exact tree stamp
 * (plus the resolved workbench root) changed; presets not present in the
 * source are left untouched. `workbenchRoot` defaults to resolveWorkbenchRoot();
 * when it resolves, `{{WORKBENCH_ROOT}}` markers in the synced composition are
 * substituted so the preset no longer carries machine-specific absolute paths.
 * Returns { synced, retired, failed }.
 */
export function syncPresetTrees(sourceRoot, targetRoot, retire = [], workbenchRoot = resolveWorkbenchRoot()) {
  const synced = []
  const retired = []
  const failed = []
  const sourceIds = existsSync(sourceRoot) ? readdirSync(sourceRoot, { withFileTypes: true }).filter((e) => e.isDirectory()).map((e) => e.name) : []
  for (const id of sourceIds) {
    const source = join(sourceRoot, id)
    const target = join(targetRoot, id)
    try {
      const stamp = `${treeStamp(source)}#${workbenchRoot ?? '-'}`
      if (readStamp(target) === stamp) {
        continue
      }
      const doc = readFileSync(join(source, 'agent.cordis.yml'), 'utf-8')
      const problems = validateAgentCordis(doc)
      if (problems.length > 0) {
        failed.push({ id, error: `agent.cordis.yml invalid: ${problems.join('; ')}` })
        continue
      }
      rmSync(target, { recursive: true, force: true })
      copyDir(source, target)
      if (workbenchRoot !== undefined) {
        const compositionPath = join(target, 'agent.cordis.yml')
        writeFileSync(compositionPath, substituteWorkbenchRoot(readFileSync(compositionPath, 'utf-8'), workbenchRoot))
      }
      writeFileSync(join(target, STAMP_FILE), stamp)
      synced.push(id)
    } catch (error) {
      failed.push({ id, error: error instanceof Error ? error.message : String(error) })
    }
  }
  for (const id of retire) {
    const target = join(targetRoot, id)
    if (existsSync(target)) {
      rmSync(target, { recursive: true, force: true })
      retired.push(id)
    }
  }
  return { synced, retired, failed }
}

function copyDir(source, target) {
  mkdirSync(target, { recursive: true })
  for (const entry of readdirSync(source, { withFileTypes: true })) {
    const from = join(source, entry.name)
    const to = join(target, entry.name)
    if (entry.isDirectory()) {
      copyDir(from, to)
    } else {
      writeFileSync(to, readFileSync(from))
    }
  }
}

/** Marker in preset compositions replaced with the workbench root at sync time. */
export const WORKBENCH_ROOT_MARKER = '{{WORKBENCH_ROOT}}'

/**
 * Derive the workbench root for path substitution. The AGENT_WORKBENCH_ROOT
 * env override wins; otherwise walk up from this module's real path (a
 * `link:` install resolves through the junction to the real tree). Returns
 * undefined when the derived root does not actually contain the impl-package
 * plugin — callers then leave the marker in place, and the preset-local
 * plugins fall back to their ancestor-walk resolution at runtime.
 */
export function resolveWorkbenchRoot(env = process.env, moduleUrl = import.meta.url) {
  const override = env.AGENT_WORKBENCH_ROOT
  if (override !== undefined && override.trim() !== '') {
    return override.trim().replace(/[\\/]+$/, '')
  }
  let dir = dirname(fileURLToPath(moduleUrl)) // <plugin>/lib
  try {
    dir = realpathSync(dir)
  } catch {
    // keep the unresolved path; the marker check below still guards us
  }
  // lib → plugin → plugins → plugin-marketplace → workbench root
  const root = dirname(dirname(dirname(dirname(dir))))
  if (!existsSync(join(root, 'plugin-marketplace', 'plugins', 'impl-package', 'scripts', 'impl_package_state.py'))) {
    return undefined
  }
  return root.replace(/\\/g, '/')
}

/** Replace the workbench-root marker in a preset file's text. */
export function substituteWorkbenchRoot(text, root) {
  if (typeof text !== 'string' || root === undefined) return text
  return text.split(WORKBENCH_ROOT_MARKER).join(root)
}

/** Model-facing announcement: what the adapter provides and its boundary. */
export const IMPL_PACKAGE_GUIDANCE =
  '本机已安装 dsh-impl-package 插件（Impl-Package 原生适配）：主控预设会通过 agent/pre-step 自动注入「当前处境 + 合法动作 + digest」' +
  '（package validate → situation.py render），并提供 typed 工具（impl_package_validate / impl_situation_render / impl_ticket_transition / ' +
  'impl_evidence_add / impl_evidence_add_batch / impl_evidence_retire_claim / impl_recovery_checkpoint / impl_recovery_judgment / impl_gate_commit / ' +
  'impl_trail_dispatch / impl_trail_escape / impl_trail_fact / impl_trail_worker_return）直接调用现有语义 CLI。' +
  'trail dispatch 须带 dispatch_id/candidate_id/mode/chosen/receipt（$dispatcher 合同），worker-return 用 of 指回 dispatch 并带唯一 return_id。' +
  'state.json 与 Git 仍是唯一权威；本插件只做执行轨迹与处境注入，不另建事实源。' +
  '原生 subagent（subagent_codex）已替代 call-codex 的进程外派发；envelope 与 receipt 规则沿用 $dispatcher 合同。'

/** Mount the plugin: sync presets, then announce through a prompt section. */
export function apply(ctx, config) {
  const enabled = config?.enabled !== false
  const announce = config?.announceToAgent !== false
  const targetRoot = join(resolveDshHome(), '.agent-presets')
  let disposeSection
  const refresh = () => {
    disposeSection?.()
    disposeSection = undefined
    if (!enabled) return
    try {
      mkdirSync(targetRoot, { recursive: true })
      const result = syncPresetTrees(bundledPresetsRoot(), targetRoot)
      for (const { id, error } of result.failed) ctx.logger?.warn?.(`dsh-impl-package: preset ${id} sync failed: ${error}`)
      if (result.synced.length > 0) ctx.logger?.info?.(`dsh-impl-package: presets synced into ${targetRoot}: ${result.synced.join(', ')}`)
      if (result.retired.length > 0) ctx.logger?.info?.(`dsh-impl-package: retired stale presets: ${result.retired.join(', ')}`)
    } catch (error) {
      ctx.logger?.warn?.(`dsh-impl-package: preset sync failed: ${error instanceof Error ? error.message : String(error)}`)
    }
    if (announce) {
      disposeSection = ctx.systemPrompt.section({
        name: 'plugin:dsh-impl-package',
        order: 150,
        text: IMPL_PACKAGE_GUIDANCE,
      })
    }
  }
  refresh()
  ctx.effect(() => () => {
    disposeSection?.()
    disposeSection = undefined
  }, 'dsh-impl-package: announcement')
}
