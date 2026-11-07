"""R12 lifecycle acceptance against a private clone; never writes formal data.

prepare while formal services run; stop them after checking their identity;
run with ports 3000/8000 free; observe browser; stop; restore formal services;
verify-formal. Only the project's existing Qdrant container is stopped/started.
No imports, upserts, collection deletes, volume deletes or model downloads.
"""
import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import sqlite3
import struct
import subprocess
import sys
import time

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth.accounts import change_account
from backend.db.connection import ROOT, make_engine
from backend.db.models import User
from backend.db.seed import password_hasher
from backend.search.qdrant import Qdrant

OUT = ROOT / 'runtime/verification/r12'
STATE = OUT / 'state.json'
REPORT = ROOT / 'docs/checks/stage1b-6-lifecycle.json'
ORIGIN = 'http://127.0.0.1:3000'
TABLES = ('users', 'documents', 'document_versions', 'pages', 'pipeline_profiles', 'index_generations', 'index_pages')
HEADERS = {'Origin': ORIGIN, 'Content-Type': 'application/json'}


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def business(path):
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro', uri=True)) as db:
        return {t: sorted(db.execute('SELECT * FROM '+t).fetchall(), key=repr) for t in TABLES}


def vector_fingerprint(collection):
    q = Qdrant()
    info = q.info(collection)
    q.check_info(info, 13)
    points = sorted(q.all_points(collection), key=lambda p: str(p['id']))
    rows = []
    for point in points:
        vectors = point['vector']['original']
        if len(vectors) != 1031 or any(len(v) != 128 for v in vectors):
            raise AssertionError('Unexpected vector shape')
        h = hashlib.sha256()
        for vector in vectors:
            h.update(struct.pack('<128f', *vector))
        rows.append({'id': point['id'], 'payload': point['payload'], 'float32_sha256': h.hexdigest()})
    if len(points) != 13:
        raise AssertionError('Unexpected point count')
    canonical = json.dumps(rows, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    return {'point_count': len(points), 'token_vectors': sum(len(p['vector']['original']) for p in points),
            'payload_and_float32_sha256': hashlib.sha256(canonical).hexdigest(), 'config': info['config']}


def docker_info():
    # Select only this Compose service. Never print the container environment/key.
    ident = subprocess.check_output(['docker', 'compose', 'ps', '-aq', 'qdrant'], cwd=ROOT, text=True).strip()
    raw = json.loads(subprocess.check_output(['docker', 'inspect', ident], text=True))[0]
    labels = raw['Config']['Labels']
    mounts = [{'name': x.get('Name'), 'destination': x['Destination']} for x in raw['Mounts']]
    if (labels.get('com.docker.compose.project') != 'layoutpatch-system'
            or labels.get('com.docker.compose.service') != 'qdrant'
            or {'name': 'layoutpatch-system-qdrant-data', 'destination': '/qdrant/storage'} not in mounts):
        raise RuntimeError('Unexpected container or volume; refusing lifecycle operation')
    return {'id': ident, 'image_id': raw['Image'], 'mounts': mounts,
            'started_at': raw['State']['StartedAt'], 'running': raw['State']['Running']}


def compose(action):
    docker_info()
    subprocess.run(['docker', 'compose', action, 'qdrant'], cwd=ROOT, check=True, capture_output=True)


def free(port):
    with socket.socket() as s:
        s.settimeout(.2)
        return s.connect_ex(('127.0.0.1', port)) != 0


def wait_url(url):
    deadline = time.monotonic()+40
    while time.monotonic() < deadline:
        try:
            if httpx.get(url, timeout=2, trust_env=False).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(.25)
    raise RuntimeError('HTTP startup deadline exceeded')


def wait_qdrant(collection):
    deadline = time.monotonic()+40
    while time.monotonic() < deadline:
        try:
            Qdrant().check_info(Qdrant().info(collection), 13)
            return
        except RuntimeError:
            time.sleep(.25)
    raise RuntimeError('Qdrant startup deadline exceeded')


def process_records(filter_text):
    # The filter is internally constructed from integer PIDs, never user text.
    command = ("Get-CimInstance Win32_Process -Filter '"+filter_text+"' | "
               "Select-Object ProcessId,ParentProcessId,CommandLine,"
               "@{Name='Created';Expression={$_.CreationDate.ToUniversalTime().ToString('o')}} | ConvertTo-Json -Compress")
    result = subprocess.check_output(['powershell', '-NoProfile', '-Command', command], text=True, encoding='utf-8').strip()
    data = json.loads(result) if result else []
    return data if isinstance(data, list) else [data]


def launch(state, name):
    if not free(8000 if name == 'backend' else 3000):
        raise RuntimeError('Occupied port; refusing to replace unknown process')
    env = {**os.environ, 'PYTHONUTF8': '1', 'NEXT_TELEMETRY_DISABLED': '1',
           'LAYOUTPATCH_DATABASE_PATH': state['database'], 'APP_ORIGIN': ORIGIN,
           'SESSION_COOKIE_SECURE': 'false', 'LAYOUTPATCH_QUERY_AUDIT_DIR': str(OUT/'queries')}
    if name == 'backend':
        args = [sys.executable, '-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1',
                '--port', '8000', '--workers', '1', '--no-access-log']
        cwd, url = ROOT, 'http://127.0.0.1:8000/health'
    else:
        args = [shutil.which('node'), 'node_modules/next/dist/bin/next', 'start', '--hostname', '127.0.0.1', '--port', '3000']
        cwd, url = ROOT/'frontend', ORIGIN
    log = OUT / (name+'-'+str(time.time_ns())+'.log')
    with log.open('w', encoding='utf-8') as stream:
        proc = subprocess.Popen(args, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    # Retain Windows creation time to protect against PID reuse in later actions.
    info = process_records('ProcessId='+str(proc.pid))[0]
    state.setdefault('owned', {})[name] = {'pid': proc.pid, 'created': info['Created']}
    write(STATE, state)
    wait_url(url)


def stop_one(state, name):
    saved = state.get('owned', {}).get(name)
    if not saved:
        return
    records = process_records('ProcessId='+str(saved['pid']))
    if records:
        p = records[0]
        if p['Created'] != saved['created']:
            raise RuntimeError('PID reused; refusing stop')
        cmd = p['CommandLine'].lower()
        expected = 'backend.main:app' if name == 'backend' else 'node_modules/next/dist/bin/next'
        if expected not in cmd:
            raise RuntimeError('Process identity mismatch; refusing stop')
        subprocess.run(['taskkill', '/PID', str(saved['pid']), '/T', '/F'], check=True, capture_output=True)
    deadline = time.monotonic()+10
    port = 8000 if name == 'backend' else 3000
    while not free(port) and time.monotonic() < deadline:
        time.sleep(.1)
    if not free(port):
        raise RuntimeError('Port did not close')
    state['owned'].pop(name, None)
    write(STATE, state)


def prepare():
    OUT.mkdir(parents=True, exist_ok=True)
    if STATE.exists():
        raise RuntimeError('Existing R12 state; inspect it, do not overwrite')
    backup = OUT/'metadata-before.sqlite3'
    if not backup.is_file():
        raise RuntimeError('Capture immutable formal baseline first')
    database = OUT/'acceptance.sqlite3'
    if database.exists():
        raise RuntimeError('Existing test database')
    with closing(sqlite3.connect(backup)) as src, closing(sqlite3.connect(database)) as dst:
        src.backup(dst)
    engine = make_engine(database)
    passwords = {u: secrets.token_urlsafe(24) for u in ('A', 'B', 'admin')}
    try:
        with Session(engine) as db, db.begin():
            for user in db.scalars(select(User)):
                user.password_hash = password_hasher.hash(passwords[user.username])
                user.must_change_password, user.active = True, True
        with closing(sqlite3.connect(database)) as db:
            db.execute('DELETE FROM auth_sessions')
            db.execute('DELETE FROM login_attempts')
            db.commit()
            collection = db.execute('SELECT collection_name FROM index_generations').fetchone()[0]
    finally:
        engine.dispose()
    state = {'database': str(database), 'passwords': passwords, 'collection': collection, 'owned': {}}
    write(STATE, state)
    current = vector_fingerprint(collection)
    if (OUT/'qdrant-before.json').exists():
        if current != read(OUT/'qdrant-before.json'):
            raise RuntimeError('Original nonempty baseline differs; investigate before retry')
    else:
        write(OUT/'qdrant-before.json', current)
    if not (OUT/'docker-before.json').exists():
        write(OUT/'docker-before.json', docker_info())
    print('Prepared R12 private clone and nonempty vector/config baseline; formal data untouched.')


def run():
    state = read(STATE)
    if not all(free(p) for p in (3000, 8000)):
        raise RuntimeError('Stop verified formal services first; test will not kill them')
    report = {'date': '2026-11-07', 'round': 'R12', 'batch': '1B-6', 'checks': [],
              'formal_password_changes': False, 'index_imports_or_upserts': 0,
              'scope': 'real production Next/Uvicorn/original GPU; isolated SQLite clone; existing nonempty Qdrant'}
    cases = []
    def check(name, ok):
        report['checks'].append({'name': name, 'passed': bool(ok)})
        write(REPORT, report)
        if not ok:
            raise AssertionError(name)
    def login(c, name):
        c.cookies.clear()
        res = c.post('/auth/login', json={'username': name, 'password': state['passwords'][name]}, headers=HEADERS)
        check(name+'_login_'+str(len(report['checks'])), res.status_code == 200)
        return res.json()
    def logout(c):
        csrf = c.get('/auth/me').json()['csrf_token']
        return c.post('/auth/logout', headers={**HEADERS, 'X-CSRF-Token': csrf})
    def search(c, name, question, case_name):
        prior = set((OUT/'queries').glob('*.json')) if (OUT/'queries').exists() else set()
        res = c.get('/search', params={'q': question, 'k': 3})
        check(case_name+'_real200', res.status_code == 200 and len(res.json().get('items', [])) == 3)
        with closing(sqlite3.connect(state['database'])) as db:
            pages = dict(db.execute('SELECT p.id,p.source_page_id FROM pages p JOIN document_versions v ON v.id=p.document_version_id JOIN documents d ON d.id=v.document_id JOIN users u ON u.id=d.owner_id WHERE u.username=?', (name,)))
        hits = res.json()['items']
        check(case_name+'_authorized_topk', all(h['page_id'] in pages for h in hits))
        fresh = set((OUT/'queries').glob('*.json'))-prior
        check(case_name+'_fresh_forward', len(fresh) == 1 and read(next(iter(fresh)))['network_attempts'] == 0)
        cases.append({'name': case_name, 'pages': pages, 'audit': str(next(iter(fresh))),
                      'items': [{k: h[k] for k in ('page_id', 'page_score')} for h in hits]})
        image = c.get(hits[0]['preview_url'])
        check(case_name+'_png_hash', image.status_code == 200 and hashlib.sha256(image.content).hexdigest() == hits[0]['render_sha256'])
        return hits[0]['preview_url']
    engine = make_engine(Path(state['database']))
    try:
        launch(state, 'backend'); launch(state, 'frontend')
        with httpx.Client(base_url=ORIGIN+'/api', timeout=240, trust_env=False) as c:
            check('initial_health_proxy', c.get('/health').json() == {'status': 'ok'})
            check('shell_real_html', 'LayoutPatch' in c.get(ORIGIN).text)
            for route in ('/auth/me', '/search?q=unauthenticated', '/pages/unknown/image', '/admin/profiles'):
                check('T01_'+route.split('?')[0], c.get(route).status_code == 401)
            spec = httpx.get('http://127.0.0.1:8000/openapi.json', trust_env=False).json()
            expected = {'/health', '/auth/login', '/auth/me', '/auth/logout', '/auth/password', '/admin/profiles', '/search', '/pages/{page_id}/image'}
            check('routes_only_current_stage', set(spec['paths']) == expected)
            for route in ('/files/raw.png', '/ocr/x', '/clear/all', '/config/update', '/admin/users'):
                check('unmounted_'+route, c.get(route).status_code == 404)
            for name in ('A', 'B', 'admin'):
                result = login(c, name)
                check(name+'_first_change_gate', result['must_change_password'] and c.get('/search', params={'q': 'gate'}).status_code == 403)
                new = secrets.token_urlsafe(24)
                response = c.post('/auth/password', json={'current_password': state['passwords'][name], 'new_password': new},
                                  headers={**HEADERS, 'X-CSRF-Token': result['csrf_token']})
                check(name+'_isolated_password_change', response.status_code == 204)
                state['passwords'][name] = new; write(STATE, state)
                check(name+'_old_session401', c.get('/auth/me').status_code == 401)
            login(c, 'A')
            check('T02_user_profiles403', c.get('/admin/profiles').status_code == 403)
            check('T05_missing_csrf403', c.post('/auth/logout', headers=HEADERS).status_code == 403)
            check('T05_wrong_origin403', c.post('/auth/logout', headers={**HEADERS, 'Origin': 'http://example.invalid'}).status_code == 403)
            check('T03_owner_parameter422', c.get('/search', params={'q': 'x', 'owner': 'B'}).status_code == 422)
            music = 'How does Frechet Music Distance compare generated music to reference recordings?'
            url_a = search(c, 'A', music, 'A_B_related_question')
            cookie_a = c.cookies.get('layoutpatch_session')
            stop_one(state, 'backend')
            check('backend_outage_proxy5xx', c.get('/health').status_code >= 500)
            launch(state, 'backend')
            check('backend_restart_session_persists', c.get('/auth/me').status_code == 200)
            check('backend_restart_preview_persists', c.get(url_a).status_code == 200)
            stop_one(state, 'frontend'); check('frontend_stop_port_free', free(3000))
            launch(state, 'frontend')
            check('frontend_restart_same_session', c.get('/auth/me').status_code == 200)
            check('frontend_restart_same_preview', c.get(url_a).status_code == 200)
            url_b = None
            with httpx.Client(base_url=ORIGIN+'/api', timeout=240, trust_env=False) as b:
                login(b, 'B'); url_b = search(b, 'B', music, 'B_before_restart')
                check('T03_A_cannot_read_B_preview404', c.get(url_b).status_code == 404)
                check('T03_B_cannot_read_A_preview404', b.get(url_a).status_code == 404)
                check('B_logout204', logout(b).status_code == 204)
            compose('stop')
            check('qdrant_container_stopped', not docker_info()['running'])
            outage = c.get('/search', params={'q': 'Explain hardware area and energy in temporal unary matrix multiplication.'})
            check('qdrant_outage_real_search503_no_items', outage.status_code == 503 and outage.json() == {'detail': 'SEARCH_UNAVAILABLE'})
            check('qdrant_outage_health_is_liveness_only', c.get('/health').status_code == 200)
            check('qdrant_outage_png_independent', c.get(url_a).status_code == 200)
            compose('start'); wait_qdrant(state['collection'])
            after = vector_fingerprint(state['collection']); write(OUT/'qdrant-after.json', after)
            check('nonempty_points_payload_float32_config_exactly_equal', after == read(OUT/'qdrant-before.json'))
            old, current = read(OUT/'docker-before.json'), docker_info()
            write(OUT/'docker-after.json', current)
            check('same_container_image_volume_new_start_time', all(old[k] == current[k] for k in ('id', 'image_id', 'mounts')) and old['started_at'] != current['started_at'])
            search(c, 'A', music, 'A_after_qdrant_restart')
            change_account(engine, 'A', 'revoke', time.time())
            check('T05_revoked_session_image401', c.get(url_a).status_code == 401)
            stop_one(state, 'backend'); launch(state, 'backend')
            check('T05_revoked_cookie_not_resurrected', c.get('/auth/me', headers={'Cookie': 'layoutpatch_session='+cookie_a}).status_code == 401)
            login(c, 'A')
            check('T05_new_session_old_preview404', c.get(url_a).status_code == 404)
            url_a = search(c, 'A', 'Where are area and energy savings reported for temporal unary matrix multiplication?', 'A_new_question_after_backend_restart')
            # Terminate only this backend's actual model child, leaving web alive.
            descendants, pending = [], [state['owned']['backend']['pid']]
            while pending:
                children = process_records('ParentProcessId='+str(pending.pop()))
                descendants.extend(children); pending.extend(p['ProcessId'] for p in children)
            models = [p for p in descendants if 'model_query_worker.py' in (p['CommandLine'] or '')]
            model_ids = {p['ProcessId'] for p in models}
            model_roots = [p for p in models if p['ParentProcessId'] not in model_ids]
            # Windows venv Python may redirect through a launcher into one real
            # interpreter. Count process trees, not identical command strings.
            check('one_actual_model_process_tree', len(model_roots) == 1 and
                  all(p['ParentProcessId'] == model_roots[0]['ProcessId'] for p in models if p not in model_roots))
            subprocess.run(['taskkill', '/PID', str(model_roots[0]['ProcessId']), '/T', '/F'], check=True, capture_output=True)
            failed = c.get('/search', params={'q': music})
            check('model_stopped503_no_replay', failed.status_code == 503 and failed.json() == {'detail': 'SEARCH_UNAVAILABLE'})
            search(c, 'A', music, 'A_model_auto_recovery')
            check('A_logout204', logout(c).status_code == 204)
            login(c, 'admin')
            check('T02_admin_profiles200', c.get('/admin/profiles').status_code == 200)
            before_empty = len(list((OUT/'queries').glob('*.json')))
            empty = c.get('/search', params={'q': 'What can the administrator read?'})
            check('T03_admin_empty_no_global_bypass', empty.status_code == 200 and empty.json()['status'] == 'empty' and not empty.json()['items'])
            check('T03_empty_no_new_forward', before_empty == len(list((OUT/'queries').glob('*.json'))))
            check('admin_logout204', logout(c).status_code == 204)
        check('formal_business_tables_equal_R12_backup', business(ROOT/'runtime/metadata.sqlite3') == business(OUT/'metadata-before.sqlite3'))
        write(OUT/'reference-cases.json', cases)
        report.update(overall='passed', reference_cases=len(cases), successful_real_forwards=len(cases),
                      browser_services='isolated services retained; use stop after browser QA')
    except BaseException as error:
        report.update(overall='failed', failure_type=type(error).__name__)
        # The failure stays in evidence. Always attempt to restore Qdrant availability.
        try:
            if not docker_info()['running']:
                compose('start'); wait_qdrant(state['collection'])
        except BaseException:
            report['qdrant_recovery_failed'] = True
        raise
    finally:
        engine.dispose(); write(REPORT, report)
    print('Passed '+str(len(report['checks']))+' lifecycle checks; private test services retained for browser QA.')


def stop():
    state = read(STATE)
    stop_one(state, 'frontend'); stop_one(state, 'backend')
    if not docker_info()['running']:
        compose('start'); wait_qdrant(state['collection'])
    print('Stopped only R12-owned test process trees; Qdrant running, formal collection untouched.')


def verify_formal():
    state = read(STATE)
    checks = []
    def check(name, ok):
        checks.append({'name': name, 'passed': bool(ok)})
        if not ok:
            raise AssertionError(name)
    check('formal_seven_business_tables_exactly_equal', business(ROOT/'runtime/metadata.sqlite3') == business(OUT/'metadata-before.sqlite3'))
    check('formal_qdrant_fingerprint_still_equal', vector_fingerprint(state['collection']) == read(OUT/'qdrant-before.json'))
    with closing(sqlite3.connect((ROOT/'runtime/metadata.sqlite3').as_uri()+'?mode=ro', uri=True)) as db:
        check('formal_sqlite_integrity_ok', db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok')
        check('formal_fk_no_violations', not db.execute('PRAGMA foreign_key_check').fetchall())
        with closing(sqlite3.connect(OUT/'metadata-before.sqlite3')) as before:
            check('formal_existing_sessions_and_login_attempts_preserved', all(
                sorted(db.execute('SELECT * FROM '+t).fetchall(), key=repr) ==
                sorted(before.execute('SELECT * FROM '+t).fetchall(), key=repr)
                for t in ('auth_sessions', 'login_attempts')))
    check('owned_test_processes_cleaned', not state.get('owned'))
    with httpx.Client(base_url=ORIGIN, timeout=10, trust_env=False) as c:
        check('formal_frontend200', c.get('/').status_code == 200)
        check('formal_proxy_health200', c.get('/api/health').json() == {'status': 'ok'})
        check('formal_unauth_search401', c.get('/api/search', params={'q': 'smoke'}).status_code == 401)
        check('formal_unauth_image401', c.get('/api/pages/unknown/image').status_code == 401)
    write(ROOT/'docs/checks/stage1b-6-formal.json', {'date': '2026-11-07', 'round': 'R12', 'checks': checks,
          'overall': 'passed', 'formal_credentials_used_or_changed': False,
          'scope': 'fresh R12 backup comparison, integrity, nonempty index and anonymous formal smoke'})
    print('Passed '+str(len(checks))+' formal restoration checks; no formal credentials used.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'run', 'stop', 'verify-formal'])
    {'prepare': prepare, 'run': run, 'stop': stop, 'verify-formal': verify_formal}[parser.parse_args().action]()
