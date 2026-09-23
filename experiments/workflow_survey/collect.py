"""Resumable public n8n template snapshot. Downloads JSON only, executes no workflows."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import subprocess
from urllib.request import Request, urlopen

BASE = 'https://api.n8n.io/templates/'

def fetch(url, attempts=3):
    for attempt in range(attempts):
        try:
            # Windows urllib transport is rejected (403) on this public endpoint;
            # the system curl transport succeeds without credentials or cookies.
            result = subprocess.run(['curl.exe', '--fail', '--location', '--silent', '--show-error',
                                     '--max-time', '60', url], capture_output=True, timeout=65, check=True)
            data = result.stdout
            return data, json.loads(data)
        except Exception:
            if attempt + 1 == attempts:
                raise
            time.sleep(2 ** attempt)

def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.part')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)

def collect_index(root, page_size):
    pages = root / 'index_pages'
    pages.mkdir(parents=True, exist_ok=True)
    rows, seen = [], set()
    offset, total, duplicates = 0, None, 0
    while total is None or offset < total:
        path = pages / f'{offset:06d}.json'
        if path.exists():
            response = json.loads(path.read_text(encoding='utf-8'))
        else:
            _, response = fetch(BASE + f'workflows?rows={page_size}&skip={offset}')
            save_json(path, response)
        total = int(response['totalWorkflows']) if total is None else total
        items = response.get('workflows', [])
        if not items:
            break
        fresh = 0
        for item in items:
            if item['id'] not in seen:
                seen.add(item['id'])
                rows.append(item)
                fresh += 1
            else:
                duplicates += 1
        print(f'INDEX offset={offset} returned={len(items)} new={fresh} unique={len(rows)} total_reported={total}', flush=True)
        if fresh == 0:
            raise RuntimeError('Pagination repeated an entire page; abort rather than claim coverage')
        offset += len(items)
    save_json(root / 'index.json', {'retrieved_at_utc': datetime.now(timezone.utc).isoformat(),
        'source': BASE, 'source_kind': 'independent current public catalog; not the original 6003 corpus',
        'pagination': {'page_size': page_size, 'reported_total_at_start': total,
                       'unique_count': len(rows), 'duplicate_entries': duplicates,
                       'caveat': 'Live ranking may change during collection; not a transactional snapshot'},
        'workflows': rows})
    return rows

def download_one(root, item):
    wid = item['id']
    path = root / 'workflows' / f'{wid}.json'
    if not path.exists():
        raw, value = fetch(BASE + f'workflows/{wid}')
        inner = value.get('workflow', {}).get('workflow')
        if not isinstance(inner, dict) or not isinstance(inner.get('nodes'), list):
            raise ValueError('No executable workflow JSON in response')
        path.parent.mkdir(parents=True, exist_ok=True)
        part = path.with_suffix('.part')
        part.write_bytes(raw)
        part.replace(path)
    raw = path.read_bytes()
    return {'id': wid, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--workers', type=int, default=6)
    p.add_argument('--page-size', type=int, default=1000)
    p.add_argument('--limit', type=int, default=0, help='0 downloads all listed free workflows')
    args = p.parse_args()
    args.root.mkdir(parents=True, exist_ok=True)
    index = args.root / 'index.json'
    rows = json.loads(index.read_text(encoding='utf-8'))['workflows'] if index.exists() else collect_index(args.root, args.page_size)
    eligible = [x for x in rows if not x.get('price') and not x.get('purchaseUrl')]
    # Prioritize known LLM integrations to make early inventory useful; final
    # target still includes every eligible template, with no outcome selection.
    def download_order(item):
        names = ' '.join(n.get('name','') for n in item.get('nodes',[])).lower()
        known_ai = any(token in names for token in ('langchain', 'openai', 'gemini', 'anthropic'))
        return (not known_ai, item['id'])
    eligible.sort(key=download_order)
    if args.limit:
        eligible = eligible[:args.limit]
    successes, failures = [], []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs = {pool.submit(download_one, args.root, item): item['id'] for item in eligible}
        for job in as_completed(jobs):
            try:
                successes.append(job.result())
            except Exception as error:
                failures.append({'id': jobs[job], 'error': str(error)[:300]})
            count = len(successes) + len(failures)
            if count % 50 == 0 or count == len(jobs):
                save_json(args.root / 'download_progress.json', {'done': count, 'target': len(jobs),
                    'successes': len(successes), 'failures': failures})
                print(f'DOWNLOAD done={count}/{len(jobs)} success={len(successes)} failures={len(failures)}', flush=True)
    save_json(args.root / 'download_manifest.json', {'successes': sorted(successes, key=lambda x:x['id']),
        'failures': failures, 'index_count': len(rows), 'eligible_count': len(eligible),
        'excluded_paid_or_purchase_link': len(rows)-sum(not x.get('price') and not x.get('purchaseUrl') for x in rows)})

if __name__ == '__main__':
    main()
