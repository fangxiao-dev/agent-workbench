/**
 * Smoke test for the dsh-impl-package preset-local plugins.
 * Runs with plain `node` against the repo's situation fixtures — no DSH host
 * needed. Exercises the pure logic: package/scripts resolution, situation
 * message composition, ticket argv building, and the host-half preset sync.
 */
import { createRequire } from 'node:module'
const require = createRequire(import.meta.url)

import { resolvePackageDir, resolveImplScripts, composeSituationMessage, countOf, buildSituationMessage } from '../presets/impl-package/situation-hook.mjs'
import {
  buildTicketArgv,
  buildTrailDispatchInvocation,
  buildTrailEscapeInvocation,
  buildTrailFactInvocation,
  buildTrailWorkerReturnInvocation,
  apply as applyImplTools,
} from '../presets/impl-package/impl-tools.mjs'
import { COMMANDS, buildRouteMessage, apply as applyCommands } from '../presets/impl-package/commands.mjs'
import { aggregateVerdicts, resolveTopology, buildBrief, parseLeafOutput, buildReviewRunArgv, leafPersona, resolvePluginRoot, READONLY_TOOLS } from '../presets/impl-package/do-review-orchestrator.mjs'
import { extractAnchor, referencesAnchor, filterAnchorTools, decidePromotion, newState, scanEvents, resetToControlled } from '../presets/impl-package/impl-anchor.mjs'
import { validateAgentCordis, syncPresetTrees, resolveDshHome, resolveWorkbenchRoot, substituteWorkbenchRoot } from '../lib/index.mjs'

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
  const text = composeSituationMessage(render, false, '[impl-package 处境]', render.selected?.protocol)
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

console.log('== trail tools ==')
const dispatchInvocation = buildTrailDispatchInvocation('S', 'P', {
  subject: 'attempt',
  worker: 'codex',
  dispatchId: 'DSP-01',
  candidateId: 'CAND-7',
  mode: 'implement',
  chosen: 'CAND-7 via subagent_codex',
  receipt: 'started subagent job job-123',
  resourceKeys: ['ticket:TKT-01'],
  situationDigest: 'a1b2c3d4e5f6',
  reviewPhase: 'initial',
  reviewTrack: 'Track A',
  reviewRecheck: true,
})
const dispatchPayload = JSON.parse(dispatchInvocation.stdinData)
check(
  'dispatch constructor builds $dispatcher payload and named flags',
  dispatchInvocation.argv.includes('trail') && dispatchInvocation.argv.includes('append')
  && dispatchInvocation.argv.includes('--situation-digest') && dispatchInvocation.argv.includes('a1b2c3d4e5f6')
  && dispatchInvocation.argv.includes('--review-phase') && dispatchInvocation.argv.includes('initial')
  && dispatchInvocation.argv.includes('--review-track') && dispatchInvocation.argv.includes('Track A')
  && dispatchInvocation.argv.includes('--review-recheck')
  && dispatchPayload.kind === 'dispatch' && dispatchPayload.subject === 'attempt'
  && dispatchPayload.worker === 'codex'
  && dispatchPayload.dispatch_id === 'DSP-01' && dispatchPayload.candidate_id === 'CAND-7'
  && dispatchPayload.mode === 'implement' && dispatchPayload.chosen === 'CAND-7 via subagent_codex'
  && dispatchPayload.outcome === 'RUNNING' && dispatchPayload.returned === false
  && dispatchPayload.receipt === 'started subagent job job-123'
  && JSON.stringify(dispatchPayload.resource_keys) === JSON.stringify(['ticket:TKT-01'])
  && dispatchPayload.situation_digest === undefined
  && dispatchPayload.review_phase === undefined && dispatchPayload.review_track === undefined,
)
threw = false
try { buildTrailDispatchInvocation('S', 'P', { subject: 'a', worker: 'w', dispatchId: 'd', candidateId: 'c', mode: 'investigate', chosen: 'x', situationDigest: 'a1b2c3d4e5f6' }) } catch { threw = true }
check('dispatch rejects missing receipt', threw)
threw = false
try { buildTrailDispatchInvocation('S', 'P', { subject: 'a', worker: 'w', dispatchId: 'd', candidateId: 'c', mode: 'deploy', chosen: 'x', receipt: 'ok', situationDigest: 'a1b2c3d4e5f6' }) } catch { threw = true }
check('dispatch rejects unknown mode', threw)
const objectReceiptInvocation = buildTrailDispatchInvocation('S', 'P', {
  subject: 'a', worker: 'w', dispatchId: 'd', candidateId: 'c', mode: 'fix', chosen: 'x', receipt: { job: 'j-1' }, situationDigest: 'a1b2c3d4e5f6',
})
check('dispatch accepts object receipt', JSON.parse(objectReceiptInvocation.stdinData).receipt?.job === 'j-1')

const escapeInvocation = buildTrailEscapeInvocation('S', 'P', {
  subject: 'attempt', deviation: 'manual', reason: 'fixture',
})
check(
  'escape constructor builds required payload',
  escapeInvocation.argv.includes('trail') && escapeInvocation.argv.includes('append')
  && JSON.stringify(JSON.parse(escapeInvocation.stdinData)) === JSON.stringify({
    kind: 'escape', subject: 'attempt', deviation: 'manual', reason: 'fixture',
  }),
)

const factInvocation = buildTrailFactInvocation('S', 'P', {
  subject: 'attempt', key: 'attempt.in_flight', value: { enabled: true },
})
const factPayload = JSON.parse(factInvocation.stdinData)
check(
  'fact constructor preserves arbitrary JSON value',
  factInvocation.argv.includes('trail') && factPayload.kind === 'fact'
  && factPayload.subject === 'attempt' && factPayload.key === 'attempt.in_flight'
  && factPayload.value?.enabled === true,
)

const workerReturnInvocation = buildTrailWorkerReturnInvocation('S', 'P', {
  subject: 'attempt',
  outcome: 'DONE',
  of: 'DSP-01',
  returnId: 'RET-01',
  codeDelta: { base: 'abc1234', head: 'def5678' },
  consumptionId: 'CONS-01',
})
const workerReturnPayload = JSON.parse(workerReturnInvocation.stdinData)
check(
  'worker-return constructor builds required payload + code_delta pair',
  workerReturnInvocation.argv.includes('trail')
  && workerReturnPayload.kind === 'worker-return' && workerReturnPayload.subject === 'attempt'
  && workerReturnPayload.outcome === 'DONE' && workerReturnPayload.of === 'DSP-01' && workerReturnPayload.return_id === 'RET-01'
  && workerReturnPayload.code_delta?.base === 'abc1234' && workerReturnPayload.code_delta?.head === 'def5678'
  && workerReturnPayload.consumption_id === 'CONS-01',
)
threw = false
try { buildTrailWorkerReturnInvocation('S', 'P', { subject: 'a', outcome: 'o', of: 'd', returnId: 'r', codeDelta: { base: 'a', head: 'b' } }) } catch { threw = true }
check('worker-return rejects codeDelta without consumptionId', threw)
threw = false
try { buildTrailWorkerReturnInvocation('S', 'P', { subject: 'a', outcome: 'o' }) } catch { threw = true }
check('worker-return rejects missing of/returnId', threw)

const registeredImplTools = []
applyImplTools({ tools: { register(definition) { registeredImplTools.push(definition) } } }, {})
const trailToolNames = ['impl_trail_dispatch', 'impl_trail_escape', 'impl_trail_fact', 'impl_trail_worker_return']
check('four typed trail tools are registered', trailToolNames.every((name) => registeredImplTools.some((tool) => tool.name === name)))
check('evidence batch + retire-claim tools are registered', registeredImplTools.some((tool) => tool.name === 'impl_evidence_add_batch') && registeredImplTools.some((tool) => tool.name === 'impl_evidence_retire_claim'))
check('generic impl_trail_append is removed', !registeredImplTools.some((tool) => tool.name === 'impl_trail_append'))
check('14 typed impl tools registered', registeredImplTools.length === 14, String(registeredImplTools.length))

const pythonSituation = readFileSync(join(workbench, 'plugin-marketplace/plugins/impl-package/scripts/situation.py'), 'utf-8')
const pythonEngine = readFileSync(join(workbench, 'plugin-marketplace/plugins/impl-package/scripts/impl_package_runtime/engine.py'), 'utf-8')
function parsePythonTuple(source, name) {
  const match = source.match(new RegExp(`^${name}\\s*=\\s*\\(([^)]*)\\)`, 'm'))
  return match === null ? [] : [...match[1].matchAll(/["']([^"']+)["']/g)].map((item) => item[1])
}
const dispatchTool = registeredImplTools.find((tool) => tool.name === 'impl_trail_dispatch')
const dispatchProperties = dispatchTool?.parameters?.properties ?? {}
const pythonDispatchModes = [...pythonEngine.matchAll(/event\["mode"\] not in \{([^}]+)\}/g)]
  .flatMap((match) => [...match[1].matchAll(/"([^"]+)"/g)].map((item) => item[1]))
check(
  'dispatch mode enum parity with Python validator',
  JSON.stringify(dispatchProperties.mode?.enum) === JSON.stringify(pythonDispatchModes),
  `JS=${JSON.stringify(dispatchProperties.mode?.enum)} Python=${JSON.stringify(pythonDispatchModes)}`,
)
check(
  'review phase enum parity with situation.py',
  JSON.stringify(dispatchProperties.reviewPhase?.enum) === JSON.stringify(parsePythonTuple(pythonSituation, 'REVIEW_PHASE_VALUES')),
)
check(
  'review track enum parity with situation.py',
  JSON.stringify(dispatchProperties.reviewTrack?.enum) === JSON.stringify(parsePythonTuple(pythonSituation, 'REVIEW_TRACK_VALUES')),
)

console.log('== protocols ==')
const protocolsPath = join(workbench, 'plugin-marketplace/plugins/impl-package/scripts/impl_package_runtime/protocols.json')
const protocols = JSON.parse(readFileSync(protocolsPath, 'utf-8'))
check('Python-side protocols.json loads', Object.keys(protocols).length > 10 && typeof protocols.default === 'string')
check('render exposes selected protocol', typeof render?.selected?.protocol === 'string' && render.selected.protocol.trim() !== '')
// coverage: every slug in situations.yaml should have an explicit protocol or the default
const situationsText = readFileSync(join(workbench, 'plugin-marketplace/plugins/impl-package/skills/dev-with-track/situations.yaml'), 'utf-8')
const slugs = [...situationsText.matchAll(/^\s*- slug:\s*([^\s]+)\s*$/gm)].map((m) => m[1])
const uncovered = slugs.filter((slug) => protocols[slug] === undefined)
check('protocol coverage (default covers rest)', uncovered.length === 0, `${uncovered.length} uncovered: ${uncovered.slice(0, 8).join(', ')}${uncovered.length > 8 ? '…' : ''}`)
if (render !== undefined) {
  const withProtocol = composeSituationMessage(render, false, '[impl-package 处境]', render.selected?.protocol)
  check('composeSituationMessage appends render protocol', withProtocol.includes('协议:') && withProtocol.includes(render.selected.protocol.slice(0, 12)))
}

console.log('== commands ==')
check('command names match registry pattern', COMMANDS.every((c) => /^[a-z][a-z0-9_-]*$/.test(c.name)), COMMANDS.map((c) => c.name).join(','))
check('command stages unique', new Set(COMMANDS.map((c) => c.stage)).size === COMMANDS.length)
check('command table matches current route map', COMMANDS.some((c) => c.stage === 'dispatcher') && COMMANDS.some((c) => c.stage === 'execution-boundaries') && COMMANDS.some((c) => c.stage === 'monitor-progress'))
check('merged/retired stages are gone', !COMMANDS.some((c) => ['subagent-driven-development', 'execution-preflight', 'standing-bookkeeper', 'verification-before-completion', 'create-task-dag', 'grilling'].includes(c.stage)))
check('command count (15 impl-* + call-codex)', COMMANDS.length === 16, String(COMMANDS.length))
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
check('persona uses prefix/suffix schema', presetDoc.includes('prefix: >-') && presetDoc.includes('suffix: Your working directory is {{cwd}}.') && !presetDoc.includes('text: >-'))
check('preset mounts the latest-line workflow executor', presetDoc.includes("name: '@deepseek-ai/dsh-workflow-worker-thread'") && !presetDoc.includes("name: '@deepseek-ai/dsh-workflow-ptc'"))
check('preset carries no machine-specific absolute paths', !/D:[\\/]/.test(presetDoc) && presetDoc.includes('{{WORKBENCH_ROOT}}'))
check('grok provider/tool removed from preset', !/grok/i.test(presetDoc))
const tmp = mkdtempSync(join(tmpdir(), 'dsh-impl-package-test-'))
try {
  const target = join(tmp, 'agent-presets')
  mkdirSync(target, { recursive: true })
  const result = syncPresetTrees(join(workbench, 'plugin-marketplace/plugins/dsh-impl-package/presets'), target)
  check('preset sync copied impl-package', result.synced.includes('impl-package'))
  // Reviewer leaves are assembled by impl_review_run dispatch (persona + toolFilter),
  // not standalone presets — the picker must only show the main preset.
  check('no standalone reviewer leaf presets', !result.synced.some((id) => id.startsWith('review-')))
  check('synced agent.cordis.yml exists', existsSync(join(target, 'impl-package/agent.cordis.yml')))
  check('synced hook exists', existsSync(join(target, 'impl-package/situation-hook.mjs')))
  check('synced tools exist', existsSync(join(target, 'impl-package/impl-tools.mjs')))
  const syncedDoc = readFileSync(join(target, 'impl-package/agent.cordis.yml'), 'utf-8')
  check('synced composition substitutes the workbench root', !syncedDoc.includes('{{WORKBENCH_ROOT}}') && syncedDoc.includes(workbench))
  const second = syncPresetTrees(join(workbench, 'plugin-marketplace/plugins/dsh-impl-package/presets'), target)
  check('second sync is a no-op (stamp based)', second.synced.length === 0)
} finally {
  rmSync(tmp, { recursive: true, force: true })
}
check('resolveDshHome default', resolveDshHome({}, 'C:/Users/test').endsWith('.dsh'))
check('resolveWorkbenchRoot env override wins and normalizes trailing separators', resolveWorkbenchRoot({ AGENT_WORKBENCH_ROOT: 'X:/wb/' }) === 'X:/wb')
check('resolveWorkbenchRoot derives the real workbench from a module URL', resolveWorkbenchRoot({}, import.meta.url) === workbench)
check('substituteWorkbenchRoot replaces all markers', substituteWorkbenchRoot('a {{WORKBENCH_ROOT}} b {{WORKBENCH_ROOT}} c', 'W') === 'a W b W c')
check('substituteWorkbenchRoot keeps text without a resolved root', substituteWorkbenchRoot('x {{WORKBENCH_ROOT}}', undefined) === 'x {{WORKBENCH_ROOT}}')

console.log('== leaf assembly (orchestrator, no standalone presets) ==')
check('no review-* preset dirs remain', !existsSync(join(workbench, 'plugin-marketplace/plugins/dsh-impl-package/presets/review-code'))
  && !existsSync(join(workbench, 'plugin-marketplace/plugins/dsh-impl-package/presets/safety-review')))
check('READONLY_TOOLS excludes write/execute', !READONLY_TOOLS.some((t) => ['write', 'edit', 'bash', 'pwsh', 'impl_ticket_transition', 'impl_gate_commit'].includes(t)))
check('main preset mounts git-readonly for leaf inheritance', presetDoc.includes('./git-readonly.mjs') && existsSync(join(workbench, 'plugin-marketplace/plugins/dsh-impl-package/presets/impl-package/git-readonly.mjs')))
const hookSource = readFileSync(join(workbench, 'plugin-marketplace/plugins/dsh-impl-package/presets/impl-package/situation-hook.mjs'), 'utf-8')
check('situation-hook skips delegated agents', hookSource.includes('delegationDepth') && hookSource.includes('> 0'))

console.log('== orchestrator ==')
const passTracks = [
  { label: 'Track A', verdict: 'PASS', required: true },
  { label: 'Track B', verdict: 'PASS', required: true },
  { label: 'Track C', verdict: 'PASS', required: true },
]
check('aggregate: all PASS → PASS', aggregateVerdicts({ tracks: passTracks }).overall === 'PASS')
check('aggregate: any FAIL → FAIL', aggregateVerdicts({ tracks: [{ label: 'A', verdict: 'FAIL', required: true }, { label: 'B', verdict: 'PASS', required: true }] }).overall === 'FAIL')
check('aggregate: any UNCERTAIN → UNCERTAIN', aggregateVerdicts({ tracks: [{ label: 'A', verdict: 'UNCERTAIN', required: true }, { label: 'B', verdict: 'PASS', required: true }] }).overall === 'UNCERTAIN')
check('aggregate: missing verdict → INCOMPLETE', aggregateVerdicts({ tracks: [{ label: 'A', verdict: 'PASS' }, { label: 'B', verdict: undefined }] }).overall === 'INCOMPLETE')
check('aggregate: terminal Safety omitted → INCOMPLETE', aggregateVerdicts({ tracks: passTracks, safety: { applicable: true, selected: false }, phase: 'terminal-final' }).overall === 'INCOMPLETE')
check('aggregate: non-terminal Safety omitted → PASS', aggregateVerdicts({ tracks: passTracks, safety: { applicable: true, selected: false }, phase: 'initial' }).overall === 'PASS')
const registry = JSON.parse(readFileSync(join(workbench, 'plugin-marketplace/plugins/impl-package/skills/do-review/references/reviewer-registry.json'), 'utf-8'))
const defaultTopology = resolveTopology(registry, { phase: 'initial', safety: { applicable: false } })
check('topology: initial default = A/C', defaultTopology.length === 2 && defaultTopology.map((t) => t.skill).join(',') === 'review-code,review-code-by-spec')
const safetyTopology = resolveTopology(registry, { phase: 'terminal-final', safety: { applicable: true } })
check('topology: terminal-final = A/B/C + Safety', safetyTopology.length === 4 && safetyTopology.map((t) => t.skill).join(',') === 'review-code,review-code-by-standards,review-code-by-spec,safety-review')
const closureTopology = resolveTopology(registry, { phase: 'finding-closure' })
check('topology: closure = single reviewer', closureTopology.length === 1)
const brief = buildBrief({ reviewRun: { target: 'x', baseSha: 'a', headSha: 'b', mode: 'N rounds', phase: 'initial', round: 1 }, phase: 'initial', round: 1 })
check('brief: common block assembled', brief.includes('Review target:') && brief.includes('Resolved base SHA: a'))
const closureBrief = buildBrief({ reviewRun: { phase: 'finding-closure' }, phase: 'finding-closure', round: 1 })
check('brief: closure brief appended', closureBrief.includes('closure verification only'))

console.log('== orchestrator dispatch ==')
const parsedLeaf = parseLeafOutput('verdict: FAIL\ncoverage: main entry + error paths\nfindings:\n- F-01 | src/app.ts:42 | P1 | unhandled error path\n- F-02 | src/db.ts:17 | P2 | missing rollback')
check('parseLeafOutput: verdict + findings', parsedLeaf.verdict === 'FAIL' && parsedLeaf.findings.length === 2 && parsedLeaf.findings[0].file === 'src/app.ts' && parsedLeaf.findings[0].line === 42)
check('parseLeafOutput: no findings', parseLeafOutput('verdict: PASS\ncoverage: all modules\nfindings: none').findings.length === 0)
const runArgv = buildReviewRunArgv('P', { repoRoot: 'R', base: 'a', head: 'b', slug: 's', mode: 'N rounds', roundCap: 3, sources: ['docs/spec.md', 'docs/decision.md'] })
check('buildReviewRunArgv: full argv', runArgv.includes('--repo-root') && runArgv.includes('--round-cap') && runArgv.filter((a) => a === '--source').length === 2 && runArgv[runArgv.length - 1] === 'docs/decision.md')
const persona = leafPersona({ label: 'Track A', skill: 'review-code' })
check('leafPersona: read-only contract + declared skill', persona.includes('review-code') && persona.includes('never write/edit') && persona.includes('git_show'))
const resolvedRoot = resolvePluginRoot('D:/CodeSpace/agent-workbench')
check('resolvePluginRoot: finds workbench plugin', typeof resolvedRoot === 'string' && /impl-package$/.test(resolvedRoot.replace(/[\\/]+$/, '')))
check('resolvePluginRoot: undefined outside', resolvePluginRoot('C:/Windows') === undefined)

console.log('== anchor ==')
const situationMessage = {
  source: { kind: 'impl-package-situation', digest: 'a1c00c2605f7' },
  content: [{ type: 'text', text: '[impl-package 处境] digest=a1c00c2605f7\n选中: attempt.record.session-resumed · basis=prose\n动作:\n  - restore-checkpoint（默认）\n验证: package validate 通过' }],
}
const anchor = extractAnchor(situationMessage)
check('extractAnchor: digest + slug', anchor.digest === 'a1c00c2605f7' && anchor.slug === 'attempt.record.session-resumed')
check('referencesAnchor: digest hit', referencesAnchor('当前处境 digest=a1c00c2605f7，继续执行', anchor) === true)
check('referencesAnchor: slug hit', referencesAnchor('按 attempt.record.session-resumed 处理', anchor) === true)
check('referencesAnchor: miss', referencesAnchor('随便说点别的', anchor) === false)
const fullTools = [
  { name: 'read' }, { name: 'write' }, { name: 'edit' }, { name: 'grep' }, { name: 'glob' },
  { name: 'impl_package_validate' }, { name: 'impl_ticket_transition' }, { name: 'impl_gate_commit' },
  { name: 'bash' }, { name: 'subagent' },
]
const narrowed = filterAnchorTools(fullTools, ['read', 'grep', 'glob', 'skill', 'impl_package_validate', 'impl_situation_render', 'subagent', 'subagent_fork', 'ask_user_question'])
check('filterAnchorTools: write/execute tools hidden', narrowed.length === 5 && !narrowed.some((t) => ['write', 'edit', 'impl_ticket_transition', 'impl_gate_commit', 'bash'].includes(t.name)))
check('decidePromotion: transparent when no situation', decidePromotion({ hasSituation: false, anchored: false, steps: 0 }, { maxAnchorSteps: 3 }) === true)
check('decidePromotion: gated without anchor', decidePromotion({ hasSituation: true, anchored: false, steps: 0 }, { maxAnchorSteps: 3 }) === false)
check('decidePromotion: anchored promotes', decidePromotion({ hasSituation: true, anchored: true, steps: 0 }, { maxAnchorSteps: 3 }) === true)
check('decidePromotion: maxAnchorSteps fallback', decidePromotion({ hasSituation: true, anchored: false, steps: 3 }, { maxAnchorSteps: 3 }) === true)
const s0 = newState()
scanEvents(s0, [
  { type: 'user/message', data: { message: situationMessage } },
  { type: 'step/start' },
  { type: 'assistant/message', data: { message: { content: [{ type: 'text', text: '处境确认 a1c00c2605f7，先 validate' }] } } },
])
check('scanEvents: anchor captured + anchored on reference', s0.hasSituation === true && s0.anchorDigest === 'a1c00c2605f7' && s0.anchored === true)
check('scanEvents: promoted after anchored', (() => { if (!s0.promoted) { s0.promoted = decidePromotion(s0, { maxAnchorSteps: 3 }) } return s0.promoted === true })())
const s1 = newState()
scanEvents(s1, [
  { type: 'user/message', data: { message: situationMessage } },
  { type: 'assistant/message', data: { message: { content: [{ type: 'text', text: '开始动手' }] } } },
  { type: 'compaction/end' },
  { type: 'assistant/message', data: { message: { content: [{ type: 'text', text: 'a1c00c2605f7' }] } } },
])
check('compaction resets anchor state (old events do not re-promote)', s1.hasCompacted === true && s1.promoted === false && s1.anchored === false && s1.steps === 0)
resetToControlled(s1)
check('resetToControlled idempotent', s1.hasCompacted === true && s1.promoted === false)

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURES`)
process.exit(failures === 0 ? 0 : 1)
