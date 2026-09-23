"""Reproduce analysis after the public workflow snapshot has been collected."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run(*args: str) -> None:
    subprocess.run([sys.executable, *args], check=True)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True, help="Report directory containing workflows/ and the structural inventory")
    args = p.parse_args()
    here = Path(__file__).resolve().parent
    root = args.root.resolve()
    run(str(here / "build_candidate_manifest.py"), "--summary", str(root / "structural_summary.json"), "--output", str(root / "candidate_final_status.json"))
    run(str(here / "sample_negative_audit.py"), "--inventory", str(root / "structural_inventory.json"), "--candidate-manifest", str(root / "candidate_final_status.json"), "--output", str(root / "negative_audit_sample.json"))
    run(str(here / "inspect_negative_sample.py"), "--root", str(root), "--sample", str(root / "negative_audit_sample.json"), "--output", str(root / "negative_audit_structural.json"))
    run(str(here / "scan_explicit_bypass.py"), "--root", str(root), "--output", str(root / "negative_audit_explicit_bypass.json"))
    run(str(here / "scan_field_projection.py"), "--root", str(root), "--output", str(root / "negative_audit_field_projection.json"))
    run(str(here / "scan_explicit_bypass.py"), "--root", str(root), "--output", str(root / "negative_audit_explicit_bypass.json"))
    run(str(here / "reviewed_slices.py"), "--root", str(root), "--manifest", str(root / "candidate_final_status.json"))
    run(str(here / "summarize_existence.py"), "--root", str(root))
    run(str(here / "summarize_batch.py"), "--root", str(root))
    run(str(here / "export_study_tables.py"), "--root", str(root))


if __name__ == "__main__":
    main()
