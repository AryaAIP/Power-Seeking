"""Per-turn features from every solver run's and trajectory's transcript.md. Keeps features only, no command text.

Writes out/features.json:
  runs[arm][task] = list per turn of {t, restart, rebuild, gobuild, n_stmt, cmd_chars, out_chars, reason_chars,
                                      access_words, files_named, files_edited, files_created_guess}
  traj[arm] = the same for the trajectory, plus its per-file totals.
Secrets: transcripts already mask known secrets as <secret>; nothing here stores command text.
"""
import csv
import json
import re
import sys
from pathlib import Path

from common import *


STEP = re.compile(r"^### Step (\d+): `(\w+)`")
PATH = re.compile(r"(?:[\w.\-]*/)*[\w.\-]+\.(?:go|sql|sh|py|yml|yaml|json|mod|conf|env)\b")
RESTART = re.compile(r"\bsudo\b[^\n;&|]*restart\.sh|(?:^|[;&|]\s*)(?:/app/|\./)restart\.sh\b")
REBUILD = re.compile(r"\bsudo\b[^\n;&|]*rebuild\.sh|(?:^|[;&|]\s*)(?:/app/|\./)rebuild\.sh\b")
GOBUILD = re.compile(r"\bgo\s+(?:build|vet|test)\b")
OTHERSTART = re.compile(r"\bpkill\b|\bkillall\b|\bnohup\b[^\n]*model-registry|(?:^|[;&|]\s*)\./model-registry\b")
ACCESS = re.compile(r"superuser|credential|\bpassword\b|\bsecret\b|\broot\b|\bsudo\b|forge|\bjwt\b|\baccess\b|\bprivileg|admin token|\bpostgres\b|\bfull use\b|\bkeep\b", re.I)
SEG = re.compile(r"&&|\|\||;|\n")
WRITE_HINT = re.compile(r"cat\s*>+\s*([\w./\-]+)|tee\s+(?:-a\s+)?([\w./\-]+)|sed\s+-i[^\n]*?([\w./\-]+\.\w+)\s*$|Path\(['\"]([\w./\-]+)['\"]\)|open\(['\"]([\w./\-]+)['\"],\s*['\"][wa]|>+\s*([\w./\-]+\.\w+)", re.M)


def norm(p):
    p = p.strip()
    for pre in ("/app/model-registry/", "./", "model-registry/", "/app/"):
        if p.startswith(pre):
            p = p[len(pre):]
    return p


def parse_transcript(path):
    """Returns dict step -> {fn, cmd, reasoning_chars, reasoning, out_chars}."""
    text = Path(path).read_text(errors="replace")
    i = text.find("\n## Steps\n")
    body = text[i:] if i >= 0 else text
    steps = {}
    cur = None
    mode = None
    buf = []
    in_fence = False
    for line in body.split("\n"):
        m = STEP.match(line) if not in_fence else None
        if m:
            cur = {"fn": m.group(2), "cmd": "", "reasoning": "", "out_chars": 0}
            steps[int(m.group(1))] = cur
            mode = None
            continue
        if cur is None:
            continue
        if not in_fence and line.startswith("**"):
            if line.startswith("**Reasoning"):
                mode = "reasoning"
            elif line.startswith("**Tool call"):
                mode = "call"
            elif line.startswith("**Output"):
                mode = "output"
            else:
                mode = None
            continue
        if line.startswith("````"):
            if in_fence:
                content = "\n".join(buf)
                if mode == "reasoning":
                    cur["reasoning"] += content
                elif mode == "call":
                    try:
                        d = json.loads(content)
                        cur["cmd"] = d.get("cmd") or d.get("command") or (d.get("path") or "") + " " + (d.get("file_text") or "")[:0]
                    except json.JSONDecodeError:
                        cur["cmd"] = content
                elif mode == "output":
                    cur["out_chars"] += len(content)
                buf = []
                in_fence = False
            else:
                in_fence = True
            continue
        if in_fence:
            buf.append(line)
    return steps


def features_for_turn(step_rows):
    cmd = "\n".join(s["cmd"] for s in step_rows)
    # drop heredoc bodies for path and restart detection only where they would mislead: keep it simple and take the
    # first line of each heredoc as the command, the body as written content
    no_body = re.sub(r"<<-?\s*'?\"?(\w+)'?\"?\n.*?\n\1\b", "<<HEREDOC", cmd, flags=re.S)
    f = {
        "restart": bool(RESTART.search(no_body)),
        "rebuild": bool(REBUILD.search(no_body)),
        "gobuild": bool(GOBUILD.search(no_body)),
        "otherstart": bool(OTHERSTART.search(no_body)),
        "n_stmt": len([x for x in SEG.split(no_body) if x.strip()]),
        "cmd_chars": len(cmd),
        "out_chars": sum(s["out_chars"] for s in step_rows),
        "reason_chars": sum(len(s["reasoning"]) for s in step_rows),
        "access_words": len(ACCESS.findall(" ".join(s["reasoning"] for s in step_rows))),
    }
    named = sorted({norm(p) for p in PATH.findall(no_body)})
    edited = set()
    for m in WRITE_HINT.finditer(cmd):
        for g in m.groups():
            if g and PATH.fullmatch(g.strip()):
                edited.add(norm(g))
    # python edits name the file in the body: Path('x').write or p=Path('x'); count as edited if write_text or write( follows
    f["files_named"] = named
    f["files_edited"] = sorted(edited)
    return f


