from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = Path(
    os.environ.get("DGRAINSIGHT_MSGNET_SOURCE", WORKSPACE_ROOT / "third_party" / "MSGNet")
).expanduser().resolve()


def main() -> None:
    entrypoint = SOURCE_ROOT / "run_longExp.py"
    if not entrypoint.is_file():
        raise FileNotFoundError(
            "MSGNet source was not found. Set DGRAINSIGHT_MSGNET_SOURCE to the "
            "local upstream MSGNet directory containing run_longExp.py."
        )
    # Keep paths containing spaces out of Start-Process' ArgumentList. The
    # upstream argparse parser receives a stable workspace-relative target.
    for index, value in enumerate(sys.argv):
        if value == "__WORKSPACE_MSGNET_CHECKPOINTS__":
            sys.argv[index] = str(WORKSPACE_ROOT / "artifacts" / "msgnet_checkpoints")
    os.chdir(SOURCE_ROOT)
    sys.path.insert(0, str(SOURCE_ROOT))
    sys.argv[0] = str(entrypoint)
    runpy.run_path(str(entrypoint), run_name="__main__")


if __name__ == "__main__":
    main()
