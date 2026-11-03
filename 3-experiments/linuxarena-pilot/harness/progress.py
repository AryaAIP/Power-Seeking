"""Print live progress of running inspect samples from the sample buffer DBs: tool calls so far, last few commands."""
import glob, json, sqlite3, sys, zlib
for db in sorted(glob.glob('/root/.local/share/inspect_ai/samplebuffer/*/*.db')):
    if len(sys.argv) > 1 and sys.argv[1] not in db: continue
    c = sqlite3.connect(db)
    try:
        rows = c.execute("select data from events order by id").fetchall()
    except Exception as e:
        print(db, e); continue
    calls, models, errs = [], 0, []
    for (d,) in rows:
        try:
            ev = json.loads(d if isinstance(d, str) else zlib.decompress(d))
        except Exception:
            try: ev = json.loads(d)
            except Exception: continue
        t = ev.get('event')
        if t == 'model': models += 1
        if t == 'tool':
            a = ev.get('arguments', {})
            calls.append(f"{ev.get('function')}: {str(a.get('command') or a.get('cmd') or a.get('path') or a)[:150]}")
        if t == 'error' or (t=='model' and ev.get('error')): errs.append(str(ev.get('error'))[:200])
    print(db.split('/')[-1][:60], 'model_calls', models, 'tool_calls', len(calls), 'errors', len(errs))
    for x in calls[-int(sys.argv[2]) if len(sys.argv) > 2 else -6:]: print('  ', x.replace('\n', ' '))
    for e in errs[-3:]: print('  ERR', e)
