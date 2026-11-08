const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');

function service(path, calls) {
  const compiled = ts.transpileModule(fs.readFileSync(path, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  });
  const context = { exports: {}, require: (name) => name.endsWith('/request')
    ? { request: (_, options) => { calls.push(options); return options; } }
    : { OpenAPI: {} } };
  vm.runInNewContext(compiled.outputText, context);
  return context.exports;
}

test('generated SDK carries document filters, cursor, and selected scope without changing library default', () => {
  const calls = [];
  const { DocumentsService } = service('lib/api/generated/services/DocumentsService.ts', calls);
  const { SearchService } = service('lib/api/generated/services/SearchService.ts', calls);
  DocumentsService.listDocuments('ＡＢＣ_100%', 2, 'cursor');
  assert.equal(calls[0].url, '/documents');
  assert.equal(calls[0].query.name, 'ＡＢＣ_100%');
  assert.equal(calls[0].query.limit, 2);
  assert.equal(calls[0].query.cursor, 'cursor');
  SearchService.searchPages('question', 3);
  assert.equal(calls[1].query.document_id, undefined);
  SearchService.searchPages('question', 3, 'selected-document-id');
  assert.equal(calls[2].query.document_id, 'selected-document-id');
  assert.equal(calls[2].query.q, 'question');
});

test('generated region SDK binds current page and JSON identity and keeps signed crop parameters', () => {
  const calls=[];
  const { PagesService }=service('lib/api/generated/services/PagesService.ts',calls);
  const body={q:'submitted question',document_version_id:'version',render_sha256:'render',index_generation:'index'};
  PagesService.getRegionStatus('page');PagesService.rankPageRegions('page',body);
  PagesService.getRegionCrop('page',3,'task','candidates','model','signed');
  assert.equal(calls[0].url,'/pages/{page_id}/regions/status');assert.equal(calls[0].method,'GET');
  assert.equal(calls[1].path.page_id,'page');assert.equal(calls[1].method,'POST');
  assert.equal(calls[1].mediaType,'application/json');assert.equal(calls[1].body,body);
  assert.equal(calls[2].path.layout_id,3);assert.equal(calls[2].query.candidate_hash,'candidates');
  assert.equal(calls[2].query.model,'model');assert.equal(calls[2].query.token,'signed');
});
