const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');
const source = fs.readFileSync('lib/workspace-lifecycle.ts', 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } });
const context = { exports: {} }; vm.runInNewContext(compiled.outputText, context);
const { RequestGeneration, privatePreviewPath } = context.exports;

test('account switch cancels work and refuses a response that wins the cancellation race', async () => {
  const generation = new RequestGeneration(); const rendered = [];
  let resolveOld; let cancelled = false;
  const stamp = generation.current();
  const old = new Promise(resolve => { resolveOld = resolve; });
  const release = generation.track(() => { cancelled = true; });
  const update = old.then(value => { if (generation.accepts(stamp)) rendered.push(value); }).finally(release);
  generation.reset(); resolveOld('private A result'); await update;
  assert.equal(cancelled, true); assert.deepEqual(rendered, []);
  const b = generation.current(); assert.equal(generation.accepts(b), true);
});
test('new query, logout and visibility lock each invalidate earlier operations', () => {
  const generation = new RequestGeneration();
  for (const operation of ['query', 'logout', 'visibility']) {
    const stamp = generation.current(); let count = 0;
    generation.track(() => { count += 1; }); generation.reset(); generation.reset();
    assert.equal(generation.accepts(stamp), false, operation); assert.equal(count, 1);
  }
});
test('preview URL cannot escape to remote hosts, static paths or unrelated endpoints', () => {
  const url = '/pages/12345678-1234-1234-1234-123456789abc/image?preview=' + 'a'.repeat(64);
  assert.equal(privatePreviewPath(url), '/api' + url);
  for (const value of ['https://evil.example'+url, '//evil.example'+url, '/files/a.png', url+'&path=x', url+'#x', url.replace('/image','/../image')]) {
    assert.throws(() => privatePreviewPath(value));
  }
});
