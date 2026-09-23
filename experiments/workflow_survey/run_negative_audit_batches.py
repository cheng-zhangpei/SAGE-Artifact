"""Run bounded, resumable LLM proposal batches for the frozen audit sample."""
import argparse
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--start", type=int, default=0)
    p.add_argument("--stop", type=int, default=64)
    p.add_argument("--count", type=int, default=4)
    p.add_argument("--workers", type=int, default=2)
    a = p.parse_args()
    script = Path(__file__).with_name("llm_negative_audit.py")
    def run(offset):
        target = a.root / "llm_negative_audit" / f"batch_{offset:03d}"
        if (target / "proposals_UNVERIFIED.json").exists():
            return offset, 0, "cached"
        target.mkdir(parents=True, exist_ok=True)
        with (target / "run.log").open("w", encoding="utf-8") as log:
            result = subprocess.run([sys.executable, str(script), "--root", str(a.root), "--offset", str(offset), "--count", str(a.count)], stdout=log, stderr=log)
        return offset, result.returncode, "ran"
    offsets = list(range(a.start, a.stop, a.count))
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        for future in as_completed([pool.submit(run, x) for x in offsets]):
            print(future.result(), flush=True)


if __name__ == "__main__":
    main()
