const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');

function loadTs(path) {
  const compiled = ts.transpileModule(fs.readFileSync(path, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  });
  const context = { exports: {}, require(name) {
    if (name === '@/lib/document-selection') return loadTs('lib/document-selection.ts');
    if (name === './document-picker') return loadTs('components/workspace/document-picker.tsx');
    return require(name);
  } };
  vm.runInNewContext(compiled.outputText, context);
  return context.exports;
}
module.exports = { loadTs };
