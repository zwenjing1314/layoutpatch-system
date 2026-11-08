const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');

function loadTs(path) {
  const compiled = ts.transpileModule(fs.readFileSync(path, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  });
  const context = { exports: {}, setTimeout, clearTimeout, require(name) {
    if (name === '@/lib/document-selection') return loadTs('lib/document-selection.ts');
    if (name === './document-picker') return loadTs('components/workspace/document-picker.tsx');
    if (name === './upload-tasks') return loadTs('components/workspace/upload-tasks.tsx');
    if (name === './region-evidence') return loadTs('components/workspace/region-evidence.tsx');
    if (name === '@/lib/task-state') return loadTs('lib/task-state.ts');
    if (name === '@/lib/region-state') return loadTs('lib/region-state.ts');
    return require(name);
  } };
  vm.runInNewContext(compiled.outputText, context);
  return context.exports;
}
module.exports = { loadTs };
