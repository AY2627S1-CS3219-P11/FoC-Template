import { after, test } from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import ts from 'typescript'

const directory = await mkdtemp(join(tmpdir(), 'order-notices-'))
const source = await readFile(new URL('../src/pages/orders/notifications.ts', import.meta.url), 'utf8')
await writeFile(join(directory, 'notifications.mjs'), ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 },
}).outputText)
const { orderNotice } = await import(join(directory, 'notifications.mjs'))
after(() => rm(directory, { recursive: true, force: true }))
const order = { id: 'order', requester_id: 'requester', courier_id: 'courier', credits: 8, status: 'open', credit_status: 'succeeded' }

test('reservation is announced only to requester on init to open', () => {
  const previous = { ...order, status: 'init' }
  assert.match(orderNotice(previous, order, 'requester').message, /8 credits have been reserved/)
  assert.equal(orderNotice(previous, order, 'courier'), null)
  assert.equal(orderNotice(order, order, 'requester'), null)
  assert.equal(orderNotice(undefined, order, 'requester'), null)
})
test('payout is announced only to courier after confirmed settlement', () => {
  const previous = { ...order, status: 'received' }
  const completed = { ...order, status: 'completed' }
  assert.match(orderNotice(previous, completed, 'courier').message, /8 credits have been added/)
  assert.equal(orderNotice(previous, completed, 'requester'), null)
  assert.equal(orderNotice(previous, { ...completed, credit_status: 'pending' }, 'courier'), null)
  assert.equal(orderNotice(completed, completed, 'courier'), null)
  assert.equal(orderNotice(undefined, completed, 'courier'), null)
})
