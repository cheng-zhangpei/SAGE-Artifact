import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


AUDIT_FILES = (
    'response.json',
    'response_truncated_8192.json',
    'generation_amendment.json',
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    study = Path(__file__).with_name('study.py')
    subprocess.run([sys.executable, str(study), '--output', str(args.output),
                    '--suite', 'full72'], check=True)
    reused = []
    for source_task in sorted((args.source / 'tasks').iterdir()):
        if not source_task.is_dir() or not (source_task / 'response.json').exists():
            continue
        target_task = args.output / 'tasks' / source_task.name
        if not target_task.exists():
            continue
        source_prompt = json.loads((source_task / 'prompt.json').read_text(encoding='utf-8'))
        target_prompt = json.loads((target_task / 'prompt.json').read_text(encoding='utf-8'))
        if source_prompt['sha256'] != target_prompt['sha256']:
            raise ValueError(f'Prompt mismatch for {source_task.name}')
        copied = []
        for name in AUDIT_FILES:
            src = source_task / name
            if src.exists():
                shutil.copy2(src, target_task / name)
                copied.append(name)
        if not (target_task / 'evaluation.json').exists():
            subprocess.run([sys.executable, str(study), '--output', str(args.output),
                            '--worker', str(target_task)], check=True)
        reused.append({'task': source_task.name, 'prompt_sha256': source_prompt['sha256'],
                       'copied': copied})
    (args.output / 'seed_audit.json').write_text(json.dumps({
        'source': str(args.source),
        'reuse_rule': 'same task id and identical frozen prompt SHA256',
        'reused_count': len(reused),
        'records': reused,
    }, indent=2), encoding='utf-8')
    print(f'Reused {len(reused)} frozen responses in {args.output}')


if __name__ == '__main__':
    main()
