const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync('static/app.js', 'utf8');
const waitSource = source.slice(source.indexOf('async function waitOperation('), source.indexOf('const runOperation'));

async function run(responses, initial = { id: 'job-1', run_id: 'run-1', status: 'pending' }) {
  const requests = [];
  const context = vm.createContext({
    S: { busy: { kind: 'analyse' } }, Date, renderOperationStatus() {},
    setTimeout: callback => callback(),
    api: async path => {
      requests.push(path);
      const response = responses.shift();
      if (response instanceof Error) throw response;
      return response;
    },
  });
  vm.runInContext(waitSource, context);
  return { result: await context.waitOperation(initial), requests };
}

(async () => {
  let actionCalls = 0;
  const restoring = vm.createContext({ S: { busy: null, restoring: true } });
  vm.runInContext(source.slice(source.indexOf('async function act('), source.indexOf('function setRun(')), restoring);
  await restoring.act('video', () => { actionCalls++; });
  assert.equal(actionCalls, 0, 'new uploads cannot race an existing run restore');
  const initial = { id: 'job-1', run_id: 'run-1', status: 'running' };
  const success = await run([
    new Error('temporary connection loss'),
    { ...initial, status: 'running' },
    { ...initial, status: 'completed', result: { run_id: 'run-1', state: 'analysed' } },
  ], initial);
  assert.equal(success.result.state, 'analysed');
  assert(success.requests.every(path => path === '/api/runs/run-1/operations/job-1'));
  await assert.rejects(() => run([{ ...initial, status: 'failed', error: { detail: 'Model unavailable', retryable: true } }]), error => error.message === 'Model unavailable' && error.retryable);
  await assert.rejects(() => run(Array.from({ length: 5 }, () => new Error('offline'))), error => error.retryable && error.message.includes('retry to reconnect'));
  const handled = await run([{ ...initial, status: 'completed', result: { state: 'needs_review', error: { message: 'Review findings' } } }]);
  assert.equal(handled.result.state, 'needs_review');
  console.log('PASS: background polling, refresh recovery, transient network retry and provider error propagation');
})().catch(error => { console.error(error); process.exitCode = 1; });
