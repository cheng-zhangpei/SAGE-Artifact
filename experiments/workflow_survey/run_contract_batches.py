"""Bounded batch driver; subprocesses inherit transient API credential environment."""
import argparse,subprocess,sys
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args()
    def run(offset):
        log=a.root/'llm_contract_pilot'/f'binary_{offset:03d}.log'
        with log.open('w',encoding='utf-8') as f:
            result=subprocess.run([sys.executable,str(Path(__file__).with_name('llm_contract_pilot.py')),
                '--root',str(a.root),'--pool','binary','--offset',str(offset),'--count','4'],stdout=f,stderr=f)
        return {'offset':offset,'returncode':result.returncode}
    with ThreadPoolExecutor(max_workers=2) as pool:
        for future in as_completed([pool.submit(run,i) for i in range(0,24,4)]):
            print(future.result(),flush=True)

if __name__=='__main__':main()
