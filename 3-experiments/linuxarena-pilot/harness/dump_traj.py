"""Dump a Control Tower .eval sample as a readable transcript plus a power-relevance scan.
Usage: python dump_traj.py <file.eval> <out_prefix>
Writes <out_prefix>.transcript.md (every step: reasoning summary, tool call, truncated output) and prints a summary.
"""
import json, re, sys
from collections import Counter
from inspect_ai.log import read_eval_log

PATTERNS = {
    'vault/secrets': r'vault|secret|token|\.env\b|credential|password|passwd|api[_-]?key',
    'sudo/privileges': r'sudoers|\bsudo\b|visudo|setuid|chmod\s+[0-7]*[4-7][0-7]{3}|chmod\s+[ug]\+s|\bsu\s|/etc/shadow|usermod|groupadd|useradd|gpasswd|\badm\b',
    'audit/logging/monitoring': r'rsyslog|syslog|auditd|/var/log|logrotate|audit',
    'security controls': r'blacklist|whitelist|security|restricted-exec|iptables|firewall|pam\.d|/etc/pam',
    'other users': r'/home/(scott|alex|josh|dev|guest|agent)|/var/lib/dotfiles/users|ldap',
    'process/service control': r'\bkill\b|pkill|systemctl|service\s|cron|restart',
    'network': r'curl|wget|nc\s|netstat|ss\s-|filebin|packages-cdn',
}

def text_of(content):
    if isinstance(content, str): return content
    out = []
    for c in content or []:
        t = getattr(c, 'type', None)
        if t == 'text': out.append(c.text)
        elif t == 'reasoning': out.append('[reasoning] ' + (c.reasoning or c.summary or '')[:1500])
    return '\n'.join(out)

def main(path, prefix):
    log = read_eval_log(path)
    s = log.samples[0]
    lines, hits, n_calls = [], Counter(), 0
    examples = {k: [] for k in PATTERNS}
    step = 0
    for m in s.messages:
        if m.role == 'assistant':
            step += 1
            lines.append(f"\n### Step {step}\n")
            txt = text_of(m.content).strip()
            if txt: lines.append(txt[:2500] + '\n')
            for tc in m.tool_calls or []:
                n_calls += 1
                args = tc.arguments
                cmd = args.get('cmd') or args.get('command') or ''
                if tc.function == 'text_editor' or tc.function in ('view','create_file','replace_text','insert_text'):
                    cmd = f"{args.get('command','')} {args.get('path','')}"
                    body = args.get('file_text') or args.get('new_str') or ''
                    lines.append(f"**{tc.function}** `{cmd}`\n```\n{str(body)[:1500]}\n```\n")
                else:
                    lines.append(f"**{tc.function}**\n```\n{str(cmd or args)[:2500]}\n```\n")
                full = f"{cmd} {json.dumps(args)[:4000]}"
                for k, p in PATTERNS.items():
                    if re.search(p, full, re.I):
                        hits[k] += 1
                        if len(examples[k]) < 12: examples[k].append(f"step {step}: {str(cmd)[:160]}".replace('\n',' '))
        elif m.role == 'tool':
            out = text_of(m.content)
            lines.append(f"<details><summary>output ({len(out)} chars)</summary>\n\n```\n{out[:1500]}\n```\n</details>\n")
        elif m.role == 'user' and step > 0:
            lines.append(f"\n> **[user/harness]** {text_of(m.content)[:600]}\n")
    open(prefix + '.transcript.md', 'w').write('\n'.join(lines))
    u = s.model_usage
    print('task', s.metadata.get('main_task', {}).get('id') if isinstance(s.metadata.get('main_task'), dict) else '', 'status', log.status)
    print('error', s.error.message[:300] if s.error else None)
    print('scores', {k: (v.value, (v.explanation or '')[:800]) for k, v in (s.scores or {}).items()})
    print('assistant_steps', step, 'tool_calls', n_calls, 'total_time', s.total_time, 'working_time', s.working_time)
    for k, v in (u or {}).items(): print('usage', k, v.input_tokens, v.output_tokens, v.input_tokens_cache_read, v.total_tokens)
    print('limit', s.limit)
    for k in PATTERNS: print(f"\n== {k}: {hits[k]}\n  " + '\n  '.join(examples[k]))

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
