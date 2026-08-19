/**
 * reviewer-fs — read-only filesystem tool row for reviewer leaf presets.
 *
 * Registers ONLY `read` (line-numbered, offset/limit), no write/edit. The
 * official `@deepseek-ai/dsh-tool-fs` unconditionally registers read+write+
 * edit, so a reviewer preset mounts this custom row instead. Reads go through
 * node:fs directly — reviewer leaves must never write, and this module has no
 * write path at all.
 *
 * Loaded as a preset-local plugin (`name: ./reviewer-fs.mjs`); uses only
 * node: builtins plus the injected `tools` service.
 */

import { readFile } from 'node:fs/promises'

export const name = 'reviewer-fs'
export const inject = ['tools']

const DEFAULT_MAX_LIMIT = 2000

/** Read a UTF-8 file and render line-numbered content (exported for tests). */
export async function readLines(filePath, offset, limit) {
  const raw = await readFile(filePath, 'utf-8')
  const text = raw.charCodeAt(0) === 0xfeff ? raw.slice(1) : raw
  const lines = text.split(/\r\n|\r|\n/)
  const start = (offset ?? 1) - 1
  const end = Math.min(lines.length, start + (limit ?? DEFAULT_MAX_LIMIT))
  const rendered = []
  for (let index = start; index < end; index += 1) {
    rendered.push(`${index + 1}: ${lines[index]}`)
  }
  return { path: filePath, offset: start + 1, lines: rendered, total: lines.length }
}

export function apply(ctx, config) {
  const maxLimit = Number.isSafeInteger(config?.maxLimit) && config.maxLimit > 0
    ? config.maxLimit
    : DEFAULT_MAX_LIMIT
  ctx.tools.register({
    name: 'read',
    description: 'Read a UTF-8 text file and return line-numbered content (read-only; reviewer leaves never write).',
    parameters: {
      type: 'object',
      additionalProperties: false,
      properties: {
        file_path: { type: 'string', description: 'Path to read, resolved by the filesystem backend.' },
        offset: { type: 'integer', minimum: 1, description: '1-based first line to return. Defaults to 1.' },
        limit: { type: 'integer', minimum: 1, maximum: maxLimit, description: `Maximum number of lines to return. Defaults to ${maxLimit}.` },
      },
      required: ['file_path'],
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          path: { type: 'string' },
          offset: { type: 'integer' },
          lines: { type: 'array', items: { type: 'string' } },
        },
        required: ['path', 'offset', 'lines'],
      },
      render: (_args, value) => [
        { type: 'text', text: value.lines.join('\n') },
      ],
    },
    async execute(args) {
      const offset = Number.isInteger(args.offset) && args.offset >= 1 ? args.offset : 1
      const limit = Number.isInteger(args.limit) && args.limit >= 1 ? Math.min(args.limit, maxLimit) : maxLimit
      return readLines(args.file_path, offset, limit)
    },
  })
}
