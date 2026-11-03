"""Extract per-run and per-step metrics from the model-run Inspect logs."""
import glob, json, sys
from datetime import datetime
from inspect_ai.log import read_eval_log

PRICE_IN, PRICE_OUT, PRICE_CACHE = 0.098e-6, 0.294e-6, 0.00294e-6  # DeepInfra fp8 on OpenRouter, $/token

def ts(x):
    return x.timestamp() if hasattr(x, "timestamp") else datetime.fromisoformat(str(x)).timestamp()

out = []
for f in sorted(glob.glob(sys.argv[1] if len(sys.argv) > 1 else "/root/work/logs/runs/*.eval")):
    log = read_eval_log(f)
    for s in log.samples or []:
        steps, model_events = [], [e for e in s.events if e.event == "model"]
        tool_events = [e for e in s.events if e.event == "tool"]
        for e in model_events:
            u = e.output.usage
            msg = e.output.message
            tcs = msg.tool_calls or []
            steps.append({
                "latency_s": round(e.working_time or 0, 2) if getattr(e, "working_time", None) else None,
                "in": u.input_tokens if u else None, "out": u.output_tokens if u else None,
                "cache_read": (u.input_tokens_cache_read or 0) if u else 0,
                "reasoning": (u.reasoning_tokens or 0) if u else 0,
                "n_tool_calls": len(tcs), "tools": [t.function for t in tcs],
                "parse_errors": sum(1 for t in tcs if t.parse_error),
                "stop": e.output.stop_reason,
                "error": e.error,
                "served_by": (e.output.metadata or {}).get("provider") if e.output.metadata else None,
            })
        tools = []
        for e in tool_events:
            res = e.result if isinstance(e.result, str) else str(e.result)
            cmd = (e.arguments or {}).get("command") or (e.arguments or {}).get("code") or (e.arguments or {}).get("path")
            tools.append({"fn": e.function, "cmd": str(cmd)[:300], "error": e.error.type if e.error else None,
                          "seconds": round(e.working_time, 2) if getattr(e, "working_time", None) else None,
                          "out_head": res[:300]})
        tin = sum(x["in"] or 0 for x in steps); tout = sum(x["out"] or 0 for x in steps); tcache = sum(x["cache_read"] for x in steps)
        cost = (tin - tcache) * PRICE_IN + tcache * PRICE_CACHE + tout * PRICE_OUT
        tm = s.metadata.get("timing", {})
        sc = (s.scores or {}).get("main_task_success")
        n_calls = sum(x["n_tool_calls"] for x in steps)
        rec = {
            "task": log.eval.task, "file": f.split("/")[-1], "status": log.status,
            "error": s.error.message[:400] if s.error else None,
            "model": log.eval.model, "served_models": sorted({e.output.model for e in model_events if e.output and e.output.model}),
            "score": sc.value if sc else None, "score_expl_tail": (sc.explanation or "")[-600:] if sc else None,
            "steps": len(steps), "tool_calls": n_calls,
            "turns_without_tool_call": sum(1 for x in steps if x["n_tool_calls"] == 0),
            "parse_errors": sum(x["parse_errors"] for x in steps),
            "tool_errors": sum(1 for t in tools if t["error"]),
            "submitted": any("submit" in x["tools"] for x in steps),
            "tokens_in": tin, "tokens_out": tout, "tokens_cache_read": tcache,
            "reasoning_tokens": sum(x["reasoning"] for x in steps),
            "est_cost_usd": round(cost, 4),
            "model_latency_s_total": round(sum(x["latency_s"] or 0 for x in steps), 1),
            "model_latency_s_median": sorted(x["latency_s"] or 0 for x in steps)[len(steps) // 2] if steps else None,
            "tool_time_s_total": round(sum(t["seconds"] or 0 for t in tools), 1),
            "sample_total_s": s.total_time, "sample_working_s": s.working_time,
            "setup_script_s": round(tm.get("setup_end", 0) - tm.get("setup_start", 0), 2) if tm else None,
            "apply_change_s": round(tm["apply_change_end"] - tm["apply_change_start"], 2) if "apply_change_end" in tm else None,
            "agent_identity": s.metadata.get("agent_identity_check"),
            "apply_change_verified": s.metadata.get("apply_change_verified"),
            "started_at": str(s.started_at), "completed_at": str(s.completed_at),
            "per_step": steps, "per_tool": tools,
        }
        out.append(rec)
json.dump(out, open("/root/work/logs/runs_analysis.json", "w"), indent=2, default=str)
for r in out:
    print({k: v for k, v in r.items() if k not in ("per_step", "per_tool", "score_expl_tail")})
