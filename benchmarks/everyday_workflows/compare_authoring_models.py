"""Create a compact comparison from completed 72-task authoring results."""

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", action="append", nargs=2, metavar=("MODEL", "JSON"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = []
    for model, path_text in args.result:
        path = Path(path_text)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("status", "COMPLETE") != "COMPLETE" or payload.get("missing"):
            raise ValueError(f"{model}: result is not complete")
        if payload.get("tasks", payload.get("expected_tasks")) != 72:
            raise ValueError(f"{model}: expected 72 tasks")
        for key, label in (("initial", "one-shot draft"),
                           ("additive_repair", "SAGE additive"),
                           ("direct_sage", "DirectSAGE")):
            value = payload["layers"]["all"][key]
            rows.append((model, label, value))
    lines = [
        "# Two-model 72-task guard-authoring comparison", "",
        "Each model authors one guard per frozen task. SAGE evaluates every draft independently.", "",
        "| Author | Arm | PASS | FAIL | UNKNOWN | DER | BBR |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for model, label, value in rows:
        lines.append(f"| {model} | {label} | {value['pass']}/72 | {value['fail']}/72 | "
                     f"{value['unknown']}/72 | {value['der_percent']:.1f}% | {value['bbr_percent']:.1f}% |")
    lines += ["", "These are paired task-level comparison points, not repeated estimates of model reliability.", ""]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
