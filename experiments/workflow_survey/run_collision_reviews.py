import argparse,subprocess,sys
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--small-retry',action='store_true');a=p.parse_args()
 def run(i):
  log=a.root/'llm_collision_second_pass'/f'batch_{i:03d}.log';log.parent.mkdir(exist_ok=True)
  count='2' if a.small_retry else '4'
  with log.open('w',encoding='utf-8') as f:r=subprocess.run([sys.executable,str(Path(__file__).with_name('llm_collision_review.py')),'--root',str(a.root),'--offset',str(i),'--count',count],stdout=f,stderr=f)
  return i,r.returncode
 with ThreadPoolExecutor(max_workers=2) as pool:
  offsets=[12,14,24,26] if a.small_retry else list(range(0,28,4))
  for f in as_completed([pool.submit(run,i) for i in offsets]):print(f.result(),flush=True)
if __name__=='__main__':main()
