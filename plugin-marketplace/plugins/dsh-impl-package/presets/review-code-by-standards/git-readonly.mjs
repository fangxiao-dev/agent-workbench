/**
 * git-readonly — read-only git tool row for reviewer leaf presets.
 *
 * Registers exactly one typed tool `git_show` — `git show <head>:<path>` for
 * immutable contract sources (the fixed ReviewRun head SHA). Non-zero exit
 * throws; never falls back to the working tree. No other git capability.
 *
 * Loaded as a preset-local plugin (`name: ./git-readonly.mjs`); uses only
 * node: builtins plus the injected subprocess/tools services.
 */

export const name = 'git-readonly'
export const inject = ['subprocess', 'tools']

const MAX_OUTPUT_BYTES = 1 << 20

export function apply(ctx) {
  ctx.tools.register({
    name: 'git_show',
    description: 'Print a repo-relative file\'s content at the given head SHA (immutable contract source; read-only).',
    parameters: {
      type: 'object',
      additionalProperties: false,
      properties: {
        head: { type: 'string', description: 'The ReviewRun resolved head SHA (full commit SHA).' },
        path: { type: 'string', description: 'Repo-relative path.' },
      },
      required: ['head', 'path'],
    },
    output: {
      schema: { type: 'object', additionalProperties: false, properties: { text: { type: 'string' } }, required: ['text'] },
      render: (_args, value) => [{ type: 'text', text: value.text }],
    },
    async execute(args, exec) {
      const cwd = typeof exec?.agent?.session?.header?.cwd === 'string' ? exec.agent.session.header.cwd : process.cwd()
      const handle = ctx.subprocess.spawn({
        argv: ['git', 'show', `${args.head}:${args.path}`],
        cwd,
        stdio: { stdin: 'ignore', stdout: { maxBytes: MAX_OUTPUT_BYTES }, stderr: { maxBytes: MAX_OUTPUT_BYTES } },
        graceMs: 3000,
      })
      const outcome = await handle.done
      let stdout = ''
      let stderr = ''
      try {
        stdout = handle.collected.stdout.readFrom(0).text
        stderr = handle.collected.stderr.readFrom(0).text
      } catch {
        // collected readers may be unavailable on some backends
      }
      if (outcome.exitCode !== 0) throw new Error(stderr || `git_show: exit ${outcome.exitCode}`)
      return { text: stdout }
    },
  })
}
