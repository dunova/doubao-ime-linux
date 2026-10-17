"""Explicit live issue #2 regression; requires the prepared official organizer.

Only artificial samples are sent. Network/model-dependent; not part of unit CI.
Run: python3 tests/integration_cleanup.py --mode compare
"""
import asyncio
import argparse
import json
from pathlib import Path
import re
import sys
import threading
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'))
from organize import Organizer, OrganizeError
from cleanup import FIND_VALUE, canonical
from runtime import STATE

CASES=[
 ('corrected-time','今天下午2点，哦不，3点开会。', ['3点'], ['2点','哦不']),
 ('corrected-date','周三提交，哦不，周四提交。', ['周四'], ['周三','哦不']),
 ('changed-predicate','周三提交，哦不，周四完成。', ['周四完成'], ['周三','提交']),
 ('corrected-quantity','采购20个，哦不，30个零件。', ['30个','零件'], ['20个','哦不']),
 ('english-time',"Let's meet at 2 this afternoon—no, at 3.", ['3','afternoon'], ['at 2','no, at']),
 ('comparison','请比较下午2点和3点的两场会议，不要取消任何一场。', ['2点','3点','两场','不要取消'], []),
 ('negations','我们不是要取消会议，也不是要减少人数。预算不能低于20万元。', ['不是要取消','不是要减少','不能低于20万元'], []),
 ('intentional-repetition','这个问题很重要，很重要，请一定记住。', ['很重要，很重要'], []),
 ('fillers-and-stutter','嗯那个我我我想说一下明天的安排，我们先讨论预算，然后再讨论人员分工。', ['预算','人员分工'], ['嗯那个','我我我']),
 ('long-passage','帮我记一下明天的安排。第一件事是下午3点开会，先讨论预算，再看人员安排。第二件事是会后把会议纪要发给王小明，预算20万元，保留两场会议作比较。哦对了，刚才说的3点不对，改成4点。不要取消任何一场会议，也不要修改预算。',
  ['4点','预算','人员安排','会议纪要','王小明','20万元','两场','不要取消','不要修改预算'], ['3点','不对','改成']),
]

def normalize(value):
    value=FIND_VALUE.sub(lambda m:canonical(m[0]),value)
    return re.sub(r'[\s，,。;；.!！？?、:：—-]+','',value).casefold()

async def main(fail_fast=False, mode='local-rules'):
    rows=[]
    modes=('official-only','local-rules') if mode=='compare' else (mode,)
    for name,text,required,forbidden in CASES:
        for selected in modes:
            organizer=Organizer(threading.Event(),local_cleanup=selected=='local-rules')
            start=time.monotonic();error=None
            try:
                await organizer.start();result=await organizer.finish(text)
            except OrganizeError as exc:
                error=str(exc);result=text  # Same accepted-transcript fallback as Session.
            finally:await organizer.close()
            compact=normalize(result)
            passed=(all(normalize(word) in compact for word in required) and
                    not any(normalize(word) in compact for word in forbidden) and
                    error in (None,'meaning-check'))
            row={'test':name,'mode':selected,'pass':passed,'input':text,'output':result,
                 'fallback':error,'seconds':round(time.monotonic()-start,2)}
            rows.append(row);print(('PASS ' if passed else 'FAIL ')+selected+': '+name+(': '+error if error else ''),flush=True)
            (STATE/'cleanup-regression.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
            if fail_fast and not passed:raise SystemExit(1)
    for selected in modes:
        results=[row for row in rows if row['mode']==selected]
        print(f'{selected}: {sum(row["pass"] for row in results)}/{len(results)}',flush=True)
    if not all(row['pass'] for row in rows):raise SystemExit(1)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--fail-fast',action='store_true')
    parser.add_argument('--mode',choices=['official-only','local-rules','compare'],default='local-rules',
        help='Compare original transcripts with optional local heuristics; a failed content check exits nonzero')
    args=parser.parse_args()
    asyncio.run(main(args.fail_fast,args.mode))
