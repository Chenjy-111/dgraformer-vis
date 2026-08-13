from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path


SOURCE_ROOT = Path(r"C:\Users\cj\Desktop\MSGNet-main")
WORKSPACE_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    # Keep paths containing spaces out of Start-Process' ArgumentList. The
    # upstream argparse parser receives a stable workspace-relative target.
    for index, value in enumerate(sys.argv):
        if value == "__WORKSPACE_MSGNET_CHECKPOINTS__":
            sys.argv[index] = str(WORKSPACE_ROOT / "artifacts" / "msgnet_checkpoints")
    os.chdir(SOURCE_ROOT)
    sys.path.insert(0, str(SOURCE_ROOT))
    sys.argv[0] = str(SOURCE_ROOT / "run_longExp.py")
    runpy.run_path(str(SOURCE_ROOT / "run_longExp.py"), run_name="__main__")


if __name__ == "__main__":
    main()
