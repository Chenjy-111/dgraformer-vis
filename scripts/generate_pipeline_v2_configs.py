"""Regenerate checked-in full Audit Config v2 files from frozen declarations."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dgraudit.v2.frozen import load_dgraformer_frozen_inputs, load_msgnet_frozen_inputs


def write(name: str, config: dict, protocol: str) -> None:
    payload = {**config, "frozen_protocol": protocol}
    path = ROOT / "configs" / name
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(path)


def main() -> None:
    dgra = load_dgraformer_frozen_inputs()[0]
    msgnet = load_msgnet_frozen_inputs(include_intervention_trajectories=False)[0]
    write("formal_audit_v2_dgraformer_etth1_frozen40.json", dgra, "dgraformer_etth1_frozen40")
    write("formal_audit_v2_msgnet_etth1_frozen14.json", msgnet, "msgnet_etth1_frozen14")


if __name__ == "__main__":
    main()
