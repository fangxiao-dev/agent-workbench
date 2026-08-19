/**
 * Smoke test for the dsh-impl-package preset-local plugins.
 * Runs with plain `node` against the repo's situation fixtures — no DSH host
 * needed. Exercises the pure logic: package/scripts resolution, situation
 * message composition, ticket argv building, and the host-half preset sync.
 */
import { createRequire } from 'node:module'
const require = createRequire(import.meta.url)

import { resolvePackageDir, resolveImplScripts, composeSituationMessage, countOf, buildSituationMessage, loadProtocols, resolveProtocol } from '../presets/impl-package/situation-hook.mjs'
import { buildTicketArgv } from '../presets/impl-package/impl-tools.mjs'
import { COMMANDS, buildRouteMessage, apply as applyCommands } from '../presets/impl-package/commands.mjs'
import { validateAgentCordis, syncPresetTrees, resolveDshHome } from '../lib/index.mjs'

import { existsSync, mkdtempSync, rmSync, writeFileSync, readFileSync, mkdirSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { spawnSync } from 'node:child_process'

let failures = 0
function check(label, ok, detail = '') {
  if (ok) {
    console.log(`  ok  ${label}`)
  } else {
    failures += 1
    console.error(`FAIL  ${label}${detail ? ` — ${detail}` : ''}`)
  }
}

const workbench = 'D:/CodeSpace/agent-workbench'
const fixture = join(workbench, 'tests/fixtures/situations/p0-session-resumed')

console.log('== resolution ==')
check('resolvePackageDir finds the fixture by ancestor walk', resolvePackageDir(fixture, '.impl-package/state.json') === fixture)
check('resolvePackageDir misses outside the repo', resolvePackageDir(join(tmpdir(), 'no-such-package-dir-xyz'), '.impl-package/state.json') === undefined)
check(
  'resolveImplScripts walks up to the workbench plugin scripts',
  existsSync(join(resolveImplScripts(fixture) ?? '', 'impl_package_state.py')),
)

console.log('== render JSON composition ==')
// capture a real render for the fixture
const renderOut = spawnSync(
  'python',
  [
    join(workbench, 'plugin-marketplace/plugins/impl-package/scripts/situation.py'),
    'render', '--package', fixture,
    '--validation-result', '{"projection_drift":false,"source":"package validate"}',
    '--json',
  ],
  { encoding: 'utf-8', cwd: workbench },
)
check('situation.py render runs against fixture', renderOut.status === 0, renderOut.stderr?.slice(0, 200))
let render
try { render = JSON.parse(renderOut.stdout) } catch { render = undefined }
check('render output parses', render !== undefined)
if (render !== undefined) {
  const text = composeSituationMessage(render, false, '[impl-package 处境]')
  console.log('--- composed message ---')
  console.log(text)
  console.log('------------------------')
  check('message contains digest', text.includes(`digest=${render.digest}`))
  check('message contains selected slug', render.selected?.slug ? text.includes(render.selected.slug) : true)
  check('message contains actions', Array.isArray(render.selected?.actions) && render.selected.actions.length > 0 ? text.includes('动作:') : true)
  check('countOf handles arrays', countOf([]) === 0)
  check('countOf handles numbers', countOf(3) === 3)
  const msg = buildSituationMessage(text, render.digest)
  check('injected message shape', msg.role === 'user' && Array.isArray(msg.content) && msg.content[0]?.type === 'text' && msg.source?.kind === 'impl-package-situation' && msg.source?.digest === String(render.digest))
}

console.log('== ticket argv ==')
const base = { packageDir: 'P', scriptsRoot: 'S' }
const satisfy = buildTicketArgv('S', 'P', { action: 'satisfy', ticket: 'TKT-01', expect: 'PENDING', revision: 'abc1234', environment: 'unit' })
check('satisfy argv', satisfy.includes('--revision') && satisfy.includes('abc1234') && satisfy.includes('--environment'))
const revalidate = buildTicketArgv('S', 'P', { action: 'needs-revalidation', ticket: 'TKT-01', expect: 'SATISFIED', claims: ['AC-1', 'AC-2'], invalidatedBy: 'regression' })
check('needs-revalidation argv', revalidate.filter((a) => a === '--claim').length === 2 && revalidate.includes('--invalidated-by'))
let threw = false
try { buildTicketArgv('S', 'P', { action: 'needs-revalidation', ticket: 'T', expect: 'SATISFIED', invalidatedBy: 'x' }) } catch { threw = true }
check('needs-revalidation rejects missing claims', threw)
threw = false
try { buildTicketArgv('S', 'P', { action: 'satisfy', ticket: 'T', expect: 'PENDING' }) } catch { threw = true }
check('satisfy rejects missing revision', threw)

console.log('== protocols ==')
const protocolsPath = join(workbench, 'plugin-marketplace/plugins/dsh-impl-package/presets/impl-package/protocols.json')
const protocols = loadProtocols(protocolsPath)
check('protocols.json loads', Object.keys(protocols).length > 10)
check('resolveProtocol hits slug', resolveProtocol(protocols, 'attempt.gate.terminal-frozen') === protocols['attempt.gate.terminal-frozen'])
check('resolveProtocol falls back to default', typeof resolveProtocol(protocols, 'no.such.slug') === 'string' && resolveProtocol(protocols, 'no.such.slug') === protocols.default)
check('loadProtocols tolerates missing file', Object.keys(loadProtocols(join(tmpdir(), 'no-protocols.json'))).length >= 0)
// coverage: every slug in situations.yaml should have an explicit protocol or the default
const situationsText = readFileSync(join(workbench, 'plugin-marketplace/plugins/impl-package/skills/dev-with-track/situations.yaml'), 'utf-8')
const slugs = [...situationsText.matchAll(/^\s*- slug:\s*([^\s]+)\s*$/gm)].map((m) => m[1])
const uncovered = slugs.filter((slug) => protocols[slug] === undefined)
check('protocol coverage (default covers rest)', uncovered.length === 0, `${uncovered.length} uncovered: ${uncovered.slice(0, 8).join(', ')}${uncovered.length > 8 ? '…' : ''}`)
if (render !== undefined) {
  const withProtocol = composeSituationMessage(render, false, '[impl-package 处境]', protocols.default)
  check('composeSituationMessage appends protocol', withProtocol.includes('协议:') && withProtocol.includes(protocols.default.slice(0, 12)))
}

console.log('== commands ==')
check('command names match registry pattern', COMMANDS.every((c) => /^[a-z][a-z0-9_-]*$/.test(c.name)), COMMANDS.map((c) => c.name).join(','))
check('command stages unique', new Set(COMMANDS.map((c) => c.stage)).size === COMMANDS.length)
const registered = []
const steered = []
applyCommands({
  commands: {
    register(def) {
      registered.push(def)
      check(`command ${def.name} has description`, typeof def.description === 'string' && def.description.length > 0)
    },
  },
})
check('all commands registered', registered.length === COMMANDS.length, `${registered.length}/${COMMANDS.length}`)
const sample = registered.find((d) => d.name === 'impl-dev-with-track')
check('handler steers a routing message', sample !== undefined && (() => {
  const result = sample.handler({ agent: { steer: (m) => steered.push(m) }, rawInput: ' TKT-03 ' })
  return result.kind === 'success' && steered.length === 1 && steered[0].role === 'user' && steered[0].content[0].type === 'text' && steered[0].content[0].text.includes('dev-with-track') && steered[0].content[0].text.includes('TKT-03') && steered[0].source.kind === 'impl-package-command'
})())
check('buildRouteMessage shape', buildRouteMessage('x', 'impl-x').role === 'user' && buildRouteMessage('x', 'impl-x').source.command === 'impl-x')

console.log('== host half ==')
const presetDoc = readFileSync(join(workbench, 'plugin-marketplace/plugins/dsh-impl-package/presets/impl-package/agent.cordis.yml'), 'utf-8')
check('agent.cordis.yml structurally valid', validateAgentCordis(presetDoc).length === 0, validateAgentCordis(presetDoc).join('; '))
const tmp = mkdtempSync(join(tmpdir(), 'dsh-impl-package-test-'))
try {
  const target = join(tmp, 'agent-presets')
  mkdirSync(target, { recursive: true })
  const result = syncPresetTrees(join(workbench, 'plugin-marketplace/plugins/dsh-impl-package/presets'), target)
  check('preset sync copied impl-package', result.synced.includes('impl-package'))
  check('synced agent.cordis.yml exists', existsSync(join(target, 'impl-package/agent.cordis.yml')))
  check('synced hook exists', existsSync(join(target, 'impl-package/situation-hook.mjs')))
  check('synced tools exist', existsSync(join(target, 'impl-package/impl-tools.mjs')))
  const second = syncPresetTrees(join(workbench, 'plugin-marketplace/plugins/dsh-impl-package/presets'), target)
  check('second sync is a no-op (stamp based)', second.synced.length === 0)
} finally {
  rmSync(tmp, { recursive: true, force: true })
}
check('resolveDshHome default', resolveDshHome({}, 'C:/Users/test').endsWith('.dsh'))

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURES`)
process.exit(failures === 0 ? 0 : 1)
