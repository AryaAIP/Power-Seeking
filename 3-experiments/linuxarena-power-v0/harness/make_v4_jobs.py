"""Print one machine's queue lines for a stage of the Nov 3 run on four machines (plans/nov3-plan-to-6am.md, "Four
machines"). Machine K runs part K of the tasks (tasks/v4_tasks_pK.txt) in every arm, so its per-step jobs find their
raw data on the same machine; the 30 trajectories are dealt out in turn. Append the output to queue/jobs.tsv there.
  python3 -I make_v4_jobs.py K start             the free check (no work) and this machine's share of the trajectories
  python3 -I make_v4_jobs.py K before            the before arm
  python3 -I make_v4_jobs.py K after A B         the after arms and their no-work runs, A and B being trajectory labels
"""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from power_paths import LAUNCH, TRAJECTORY  # noqa: E402

k, stage, rest = int(sys.argv[1]), sys.argv[2], sys.argv[3:]
n_tasks = lambda f: sum(1 for ln in (HERE / "tasks" / f).read_text().splitlines() if ln.startswith("model_registry"))  # noqa: E731


def line(label: str, envs: int, task_file: str, par: int, args: str, purpose: str) -> str:
    return f'{label}\t{envs}\tPURPOSE="{purpose}" bash {LAUNCH} {label} tasks/{task_file} {par} {args}'


if stage == "start":
    f = f"v4_free_check_p{k}.txt"
    print(line(f"nowork-v4-S0-p{k}", n_tasks(f), f, n_tasks(f), "-p solver_user=dev -p solve=false",
               f"No-work runs from the untouched machine, part {k} of 4: H = 0, the free check of the new tasks, the machine check"))
    traj = subprocess.run([sys.executable, "-I", str(HERE / "make_traj_jobs.py")], capture_output=True, text=True, check=True)
    for i, ln in enumerate(traj.stdout.splitlines()):
        if i % 4 == k - 1:
            print(ln)
elif stage == "before":
    f = f"v4_tasks_p{k}.txt"
    print(line(f"v4-before-p{k}", n_tasks(f), f, n_tasks(f), "-p solver_user=dev",
               f"The before arm, part {k} of 4: the solver from the untouched machine"))
elif stage == "after":
    a, b = rest
    f = f"v4_tasks_p{k}.txt"
    for arm, traj, note in (("A", a, ""), ("B", b, " -p handover_note=stop")):
        rep = f"-p solver_user=dev -p traj={TRAJECTORY / (traj + '.eval')} -p traj_user=dev -p traj_cmd_bug=false"
        print(line(f"v4-after{arm}-p{k}", n_tasks(f), f, n_tasks(f), f"{rep} -p context=kept{note}",
                   f"The after-{arm} arm, part {k} of 4: replay {traj}, then the solver continues its chat"))
        print(line(f"nowork-v4-after{arm}-p{k}", n_tasks(f), f, n_tasks(f), f"{rep} -p solve=false",
                   f"No-work runs after {traj}, part {k} of 4: H = 0 for the after-{arm} arm, and the replay check"))
else:
    sys.exit(__doc__)
