"""R22 final document/evidence consistency; read-only DB, no model or credentials."""
import ast
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import subprocess
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'docs/checks/r22-document-checks.json'


def read(relative):
    return json.loads((ROOT / relative).read_text(encoding='utf-8'))


def git(*args):
    return subprocess.check_output(['git', '-c', 'core.quotepath=false', *args], cwd=ROOT).decode('utf-8').strip()


def main():
    checks = []

    def check(name, condition):
        checks.append({'name': name, 'passed': bool(condition)})

    before = read('docs/checks/stage2-6-preflight.json')
    summary = read('docs/checks/stage2-6-verification.json')
    check('R22_stage2_6_applicable_exit_and_manifest_paths', summary['round'] == 'R22' and summary['stage'] == '2-6'
          and summary['overall'] == 'passed_applicable_stage2_exit'
          and all((ROOT / p).is_file() for group in ('modified_code_files', 'updated_documents', 'generated_evidence_files', 'screenshots')
                  for p in summary.get(group, [])))
    check('HEAD_unchanged', git('rev-parse', 'HEAD') == before['head'])
    check('nothing_staged', not git('diff', '--cached', '--name-only'))
    diff = subprocess.run(['git', 'diff', '--check'], cwd=ROOT, capture_output=True)
    check('git_diff_check', diff.returncode == 0)
    protected = {p: h for p, h in before['protected'].items()
                 if p == '.gitignore' or p.startswith('docs/过程记录/')}
    check('six_historical_learning_files_and_ignore_unchanged', len(protected) == 7 and all(
        hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h for p, h in protected.items()))

    document_paths = summary['updated_documents']
    link_count = 0
    for relative in document_paths:
        path = ROOT / relative
        check('document_exists_' + relative, path.is_file())
        content = path.read_text(encoding='utf-8')
        if '过程记录/' not in relative:
            check('current_R22_entry_' + relative, 'R22' in content[:1800])
        missing = []
        for target in re.findall(r'!?\[[^\]\n]*\]\(([^\n)]+)\)', content):
            target = unquote(target.strip('<>').split('#', 1)[0])
            if not target or '://' in target or target.startswith(('mailto:', 'app:')):
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.is_file() and resolved != REPORT:
                missing.append(target)
            link_count += 1
        check('all_local_links_' + relative, not missing)
        if missing:
            checks[-1]['missing'] = missing

    titles = []
    speech_counts = {}
    for relative in document_paths[-2:]:
        content = (ROOT / relative).read_text(encoding='utf-8')
        found = re.findall(r'^## 2026-11-08｜R22｜2-6｜(S\d\d)：([^\n]+)$', content, re.M)
        titles.append(found)
        check('six_R22_steps_' + relative, [s for s, _ in found] == [f'S{i:02}' for i in range(1, 7)])
        if relative.endswith('08_2逐步口述稿.md'):
            speech_counts = {s: len(re.sub(r'\s', '', body)) for s, body in re.findall(
                r'^## 2026-11-08｜R22｜2-6｜(S\d\d)：[^\n]+\n(.*?)(?=^## |\Z)', content, re.M | re.S)}
    check('paired_technical_and_speech_titles', titles[0] == titles[1])
    check('all_six_speeches_60_to_100_characters', len(speech_counts) == 6
          and all(60 <= n <= 100 for n in speech_counts.values()))
    runbook = (ROOT / 'docs/stage2-6-runbook.md').read_text(encoding='utf-8')
    check('runbook_no_pending_exit_claim', '真实闭环/浏览器/最终保护尚未完成前' not in runbook)
    roadmap = (ROOT / 'docs/项目开发阶段规划与任务.md').read_text(encoding='utf-8')
    check('roadmap_next_only_3_1', '**下一唯一开发批：3-1，用户管理。' in roadmap
          and '尚无本系统新PDF解析通过证据' not in roadmap and '效果/高亮未验' not in roadmap)

    expected = {'http': 109, 'browser': 26, 'recovery-before': 6, 'recovery-after': 21, 'legacy': 18, 'protection': 86}
    for name, count in expected.items():
        report = read(f'docs/checks/stage2-6-{name}.json')
        check('evidence_' + name, report['overall'].startswith('passed')
              and len(report['checks']) == count and all(c['passed'] for c in report['checks']))
    reference = read('docs/checks/stage2-6-page-reference.json')
    original = read('runtime/verification/r22/page-reference-original-metadata.json')
    check('official_reference_results_unchanged_by_metadata_clarification',
          reference['cases'] == original['cases'] and reference['full_tensors_checked'] == original['full_tensors_checked']
          and reference['atol'] == original['atol'] and reference['rtol'] == original['rtol'])
    check('reference_process_and_whole_round_encoding_counts_distinguished', reference['reference_process_page_encodings'] == 0
          and reference['R22_actual_page_forwards'] == 23 and 'page_encodings' not in reference)
    costs = read('docs/checks/stage2-6-cost.json')
    check('receipt_backed_cost_counts', (costs['actual_page_forwards'], costs['all_actual_query_encodings'],
          costs['actual_D_forwards'], costs['D_cache_hits'], costs['actual_MinerU_pages'], costs['actual_ONNX_runs'])
          == (23, 24, 7, 7, 23, 294))

    rows = [json.loads(line) for line in (ROOT / 'runtime/verification/r22/qdrant-scope.jsonl').read_text('utf-8').splitlines() if line.strip()]
    sizes = []
    db_path = ROOT / 'runtime/verification/r22/metadata.sqlite3'
    with sqlite3.connect(f'file:{db_path.as_posix()}?mode=ro', uri=True) as db:
        for i, row in enumerate(rows, 1):
            body = row['body_without_query']
            conditions = body['filter']['must']
            ids = next(c['has_id'] for c in conditions if 'has_id' in c)
            fields = {c['key']: c['match'] for c in conditions if 'key' in c}
            versions = fields['document_version_id']['any']
            index = fields['index_generation']['value']
            profile = fields['profile_id']['value']
            sizes.append(len(ids))
            check(f'Qdrant_{i}_exact_Top3_before_return', row['method'] == 'POST' and row['path'].endswith('/points/query')
                  and body['limit'] == 3 and body['params']['exact'] is True and body['using'] == 'original'
                  and 'query' not in body and set(row['returned_ids']) <= set(ids) and len(row['returned_ids']) == 3)
            actual = db.execute('SELECT p.id, p.document_version_id, v.document_id FROM pages p '
                                'JOIN document_versions v ON v.id=p.document_version_id WHERE p.id IN ('
                                + ','.join('?' for _ in ids) + ')', ids).fetchall()
            selected_versions = {r[1] for r in actual}
            index_profile = db.execute('SELECT profile_id FROM index_generations WHERE id=?', (index,)).fetchone()
            expected_ids = {r[0] for r in db.execute('SELECT p.id FROM pages p JOIN index_pages ip ON ip.page_id=p.id '
                                                   'WHERE ip.index_id=? AND p.document_version_id IN ('
                                                   + ','.join('?' for _ in versions) + ')', [index, *versions])}
            check(f'Qdrant_{i}_scope_matches_selected_complete_version', len(actual) == len(ids) == len(set(ids))
                  and selected_versions == set(versions) and len({r[2] for r in actual}) == 1
                  and index_profile == (profile,) and set(ids) == expected_ids)
    check('six_audited_requests_exact_scope_sizes', sizes == [12, 5, 8, 12, 11, 12])

    changed = git('diff', '--name-only').splitlines() + git('ls-files', '--others', '--exclude-standard').splitlines()
    parsed = []
    for relative in changed:
        if relative.endswith('.py'):
            ast.parse((ROOT / relative).read_text(encoding='utf-8-sig'), filename=relative)
            parsed.append(relative)
    check('changed_Python_syntax', bool(parsed))
    new_docs = [ROOT / 'docs/stage2-6-runbook.md', REPORT, *sorted((ROOT / 'docs/checks').glob('stage2-6-*'))]
    ignored = [p.relative_to(ROOT).as_posix() for p in new_docs if p.is_file() or p == REPORT]
    result = subprocess.run(['git', 'check-ignore', '--', *ignored], cwd=ROOT, capture_output=True)
    check('original_ignore_rule_for_new_docs_preserved', result.returncode == 0
          and len(result.stdout.decode('utf-8').splitlines()) == len(ignored))
    payload = {'round': 'R22', 'date': '2026-11-08', 'stage': '2-6',
               'overall': 'passed' if all(c['passed'] for c in checks) else 'failed', 'checks': checks,
               'speech_characters': speech_counts, 'local_file_links': link_count, 'python_files_parsed': len(parsed),
               'qdrant_logged_requests': len(rows), 'qdrant_scope_sizes': sizes,
               'scope_note': 'Only six later actual retrieval requests have these network-body logs. The first four on the earlier 8001 module are covered by HTTP/receipt evidence, not claimed to have this audit log. No new model inference or service restart during this document check.'}
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'overall': payload['overall'], 'checks': len(checks), 'speech_characters': speech_counts,
                      'local_links': link_count, 'qdrant_scope_sizes': sizes,
                      'failed': [c for c in checks if not c['passed']]}, ensure_ascii=False))
    if payload['overall'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
