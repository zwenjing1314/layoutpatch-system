"""Run web unittest and torch/pytest contracts in their separate frozen environments."""
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'runtime/verification/r21'


def main():
    program="""import pathlib,unittest
names=['tests.'+p.stem for p in sorted(pathlib.Path('tests').glob('test_*.py')) if p.stem!='test_retrieval_contract']
suite=unittest.defaultTestLoader.loadTestsFromNames(names)
result=unittest.TextTestRunner(verbosity=1).run(suite)
raise SystemExit(not result.wasSuccessful())"""
    commands=[('backend-final',[sys.executable,'-B','-c',program]),
        ('model-final',[str(ROOT/'.venv/Scripts/python.exe'),'-B','-m','pytest','tests/model/test_d_contract.py','tests/test_retrieval_contract.py','-q'])]
    results=[]
    for name,command in commands:
        start=time.perf_counter();target=OUT/(name+'.log')
        with target.open('x',encoding='utf-8') as stream:
            completed=subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
        results.append({'name':name,'exit_code':completed.returncode,'seconds':time.perf_counter()-start,'log':target.relative_to(ROOT).as_posix(),'tail':target.read_text('utf-8').splitlines()[-5:]})
        print(name,completed.returncode,results[-1]['tail'])
    report={'round':'R21','overall':'passed' if all(r['exit_code']==0 for r in results) else 'failed','runs':results,
        'scope':'Web authorization doubles separated from model synthetic tests; real inference reports are separate. No frontend code/API schema/dependency changes; no new browser/build claim.'}
    with (ROOT/'docs/checks/stage2-5-tests.json').open('x',encoding='utf-8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2)
    assert report['overall']=='passed'


if __name__=='__main__':main()
