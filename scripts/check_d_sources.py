"""Verify fixed deployment selection/provenance and aggregate recorded R21 costs."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def read(path):return json.loads(path.read_text('utf-8'))


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    old=ROOT.parent/'layoutpatch';checks=[]
    def check(name,value):
        checks.append({'name':name,'passed':bool(value)})
        assert value,name
    manifest=read(old/'artifacts/route_v2_external/preparation_v1/20261007_152240/weights.json')['D-no-text']
    selection=old/'runs/retrieval/route_v2_exp3_attribution/20261007_135013/checkpoint_selection.json'
    check('source_val_selection_file_identity',digest(selection)==manifest['selection_sha256'])
    check('original_experiment_config_identity',digest(old/manifest['config'])==manifest['config_sha256'])
    seed=next(w for w in manifest['weights'] if w['seed']==0)
    selected=read(selection)['D-no-text']['0']
    check('prespecified_lowest_seed_and_selected_epoch1',seed['selected_epoch']==selected['best_epoch']==1 and seed['selection_role']=='source_val')
    check('selected_checkpoint_and_local_copy_identical',digest(old/seed['checkpoint'])==selected['checkpoint_sha256']==seed['sha256']==digest(ROOT/'runtime/models/d-no-text/seed_0_epoch_01.pt'))
    provenance=read(ROOT/'backend/algorithms/d_core/SOURCE.json')
    for name,record in provenance['files'].items():
        check('migrated_'+name,digest(ROOT/'backend/algorithms/d_core'/name)==record['migrated_sha256'])
        check('origin_'+name,digest(ROOT.parent/'layoutpatch-evidence/src/layoutpatch'/record['source'])==record['source_sha256']==digest(old/'src/layoutpatch'/record['source']))
    real=read(ROOT/'docs/checks/stage2-5-real.json')
    receipts=[read(p) for p in (ROOT/'runtime/verification/r21/regions').glob('*.json')]
    profile=digest(ROOT/'configs/d_no_text_local.json')
    check('all_current_real_receipts_same_d_profile',len(receipts)==12 and all(r['regions']['d_profile_sha256']==profile for r in receipts))
    check('current_consistency_profile_matches',read(ROOT/'docs/checks/stage2-5-consistency.json')['d_profile_sha256']==profile)
    cost={'actual_new_query_forwards_regions':12,'actual_new_query_forwards_search_regression':4,
        'query_worker_pids':sorted({r['worker_pid'] for r in receipts}|set(read(ROOT/'docs/checks/stage2-5-search.json')['worker_pids'])),
        'real_mineru_candidate_d_forwards':11,'region_query_encode_ms':sum(r['encode_ms'] for r in receipts),
        'd_cpu_forward_ms':sum(p['result']['d_forward_ms'] for p in real['pages']),
        'gpu_peak_allocated_bytes_recorded':max(r['peak_allocated_bytes'] for r in receipts),
        'development_comparison_runs':3,'development_original_forwards_total':9,'development_migrated_forwards_total':9,
        'real_receipt_original_reference_forwards':12,'cache_only_replays_without_d_forward':2,
        'new_page_encoding':0,'new_mineru_parsing':0,'training':0,
        'limits':'Peak is worker-reported CUDA allocated, not total process/CPU memory. D forward time excludes hashing/cache I/O/layout assembly/query/load. Three development comparison runs include two interim guards/profile revisions; final report uses current profile. Synthetic test forwards and repeated test invocations remain in logs and are not deployment-effectiveness/performance measurements.'}
    report={'round':'R21','overall':'passed','checks':checks,'cost':cost,'deployment_profile_sha256':profile,
        'checkpoint_bytes':(ROOT/'runtime/models/d-no-text/seed_0_epoch_01.pt').stat().st_size,'license':provenance['license'],
        'interpretation':'Source_val historical selection identity verified, no retraining or external seed selection; no effectiveness metric recomputed'}
    with (ROOT/'docs/checks/stage2-5-sources.json').open('x',encoding='utf-8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2)
    print(json.dumps({'checks':len(checks),'profile_sha256':profile,'cost':cost},ensure_ascii=False))


if __name__=='__main__':main()
