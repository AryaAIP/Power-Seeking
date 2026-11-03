"""Where the experiment's files live on this machine. Every Python script takes its paths from here, and the bash
scripts from paths.sh, which has the same defaults, so the harness runs on any machine. Each location can be set
with an environment variable; the defaults are the original WSL set-up (as root, ~ is /root).

  POWER_V0_HOME  the working folder outside the repository: data/, queue/, config/, trajectory/, harness/ (the
                 copy sync.sh makes, which is the one that runs) and src/control-tower/. Default ~/power-v0
  POWER_V0_DATA  the raw data: .eval logs, snapshots, database dumps. Default $POWER_V0_HOME/data
  POWER_V0_CT    the Control Tower checkout. Default $POWER_V0_HOME/src/control-tower
  POWER_V0_EXP   the experiment folder in the repository, which holds runs/, findings/ and viz/. Default: the
                 folder above this file when it runs from the repository; in the synced copy, the folder sync.sh
                 wrote into its exp-dir file
"""

import os
from pathlib import Path

HOME = Path(os.environ.get("POWER_V0_HOME") or Path.home() / "power-v0")
DATA = Path(os.environ.get("POWER_V0_DATA") or HOME / "data")
CT = Path(os.environ.get("POWER_V0_CT") or HOME / "src" / "control-tower")
QUEUE = HOME / "queue"
CONFIG = HOME / "config"
TRAJECTORY = HOME / "trajectory"
LAUNCH = HOME / "harness" / "launch.sh"


def _exp() -> Path:
    if os.environ.get("POWER_V0_EXP"):
        return Path(os.environ["POWER_V0_EXP"])
    here = Path(__file__).resolve().parent
    if (here.parent / "runs" / "runs-registry.md").is_file():  # running from the repository
        return here.parent
    recorded = here / "exp-dir"  # written by sync.sh into the synced copy
    if recorded.is_file():
        return Path(recorded.read_text().strip())
    raise SystemExit(f"can't find the experiment folder from {here}: run sync.sh from the repository, or set POWER_V0_EXP")


EXP = _exp()
RUNS = EXP / "runs"  # the exported records
