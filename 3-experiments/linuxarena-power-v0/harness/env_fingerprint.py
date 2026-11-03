#!/usr/bin/env python3
"""Fingerprint a model_registry stack's state, and compare two fingerprints.

  python3 -I env_fingerprint.py capture <app_container> <out.tsv> [--also-paths <other.tsv>]
  python3 -I env_fingerprint.py compare <a.tsv> <b.tsv> [--ignore-section X ...]   # exit 0 equal, 1 not

Runs on the WSL host as root. Output lines are `section<TAB>key<TAB>value`, sorted, for the
sections file, db, s3, proc, service, net. No secret is ever recorded or printed: environment
values become one hash, password-like parts of process args are redacted, password hashes are
never read, and the MinIO admin login stays inside the MinIO container.
From Python: capture(cid, also_paths=None) -> [(section, key, value)], compare(a, b) -> dict.
"""
import argparse, collections, concurrent.futures, fnmatch, hashlib, json, os, re, socket, stat, subprocess, sys, time

EXCLUDE = ('/tmp/model-registry.log',)      # fnmatch patterns of volatile paths, never fingerprinted
NET_IGNORE = ('127.0.0.11:',)               # Docker's embedded DNS listens on a random port per container
PROC_IGNORE = re.compile(r'env_fingerprint')
ENV_HASH_SKIP = (b'HOSTNAME',)              # differs per container; left out of the service env hash (name kept)
SERVICE_BIN = '/app/model-registry/model-registry'
MINIO = os.environ.get('FP_MINIO_CONTAINER', 'shared-minio')   # override only for tests
BUCKETS = ('models', 'backups')             # buckets are <role>-<T>; keys use the role so stacks compare
PG_SYS = "('pg_catalog','information_schema','pg_toast')"
TYPES = {stat.S_IFREG: 'reg', stat.S_IFDIR: 'dir', stat.S_IFLNK: 'lnk', stat.S_IFCHR: 'chr',
         stat.S_IFBLK: 'blk', stat.S_IFIFO: 'fifo', stat.S_IFSOCK: 'sock'}
REDACT = [(re.compile(r'(://[^/\s:@]*:)[^@\s]*@'), r'\1REDACTED@'),
          (re.compile(r'(?i)((?:password|passwd|pwd|token|secret|apikey|api_key)[=:]\s*)\S+'), r'\1REDACTED')]
TIMINGS = {}


def run(cmd, inp=None, check=True):
    r = subprocess.run(cmd, input=inp, capture_output=True, text=True)
    if check and r.returncode:   # never echo stderr: it may come from a container holding secrets
        raise RuntimeError(f'{" ".join(cmd[:2])} exit {r.returncode}')
    return r


def esc(s):
    return s.replace('\\', '\\\\').replace('\t', '\\t').replace('\n', '\\n').replace('\r', '\\r')


def sha_file(p, nofollow=True):
    h = hashlib.sha256()
    try:
        fd = os.open(p, os.O_RDONLY | os.O_NONBLOCK | (os.O_NOFOLLOW if nofollow else 0))
        with os.fdopen(fd, 'rb') as f:
            for b in iter(lambda: f.read(1 << 20), b''):
                h.update(b)
    except OSError:
        return 'ERR'
    return h.hexdigest()


# ---------------------------------------------------------------- file
def fmeta(root, rel, upper=None):
    p = root + rel
    try:
        st = os.lstat(p)
    except (FileNotFoundError, NotADirectoryError):
        return 'absent'
    t = TYPES.get(stat.S_IFMT(st.st_mode), 'other')
    f = [f'type={t}', f'mode={stat.S_IMODE(st.st_mode):04o}', f'uid={st.st_uid}', f'gid={st.st_gid}']
    if t == 'reg':
        f += [f'size={st.st_size}', 'sha256=' + sha_file(p)]
    elif t == 'lnk':
        f.append('target=' + esc(os.readlink(p)).replace(' ', '\\x20'))
    elif t in ('chr', 'blk'):
        f.append(f'rdev={os.major(st.st_rdev)}:{os.minor(st.st_rdev)}')
    try:
        names = sorted(os.listxattr(p, follow_symlinks=False))
    except OSError:
        names = []
    if names:   # e.g. file capabilities (security.capability)
        h = hashlib.sha256()
        for n in names:
            h.update(n.encode() + b'=' + os.getxattr(p, n, follow_symlinks=False) + b'\0')
        f.append('xattr=' + h.hexdigest()[:16])
    if upper and t == 'dir':
        try:
            if os.getxattr(upper + rel, 'trusted.overlay.opaque', follow_symlinks=False) == b'y':
                f.append('opaque')
        except OSError:
            pass
    return ' '.join(f)


def unoct(s):
    return re.sub(r'\\([0-7]{3})', lambda m: chr(int(m.group(1), 8)), s)


def overlay(pid):
    upper, mounts = None, []
    with open(f'/proc/{pid}/mountinfo') as fh:
        for line in fh:
            mp = unoct(line.split(' ')[4])
            if mp == '/':
                for o in line.split(' - ', 1)[1].split(' ', 2)[2].strip().split(','):
                    if o.startswith('upperdir='):
                        upper = unoct(o[9:])
            else:
                mounts.append(mp)
    if not upper:
        raise RuntimeError('no overlay upperdir for /')
    return upper, mounts


def files(pid, also=()):
    root = f'/proc/{pid}/root'
    upper, mounts = overlay(pid)
    excluded = lambda rel: any(fnmatch.fnmatchcase(rel, pat) for pat in EXCLUDE)
    in_mount = lambda rel: any(rel == m or rel.startswith(m.rstrip('/') + '/') for m in mounts)
    out = {}
    for d, dirs, names in os.walk(upper):
        rd = d[len(upper):] or '/'
        for n in dirs + names:
            rel = os.path.join(rd, n)
            if excluded(rel):
                continue
            out[rel] = 'mount' if in_mount(rel) else fmeta(root, rel, upper)
        dirs[:] = [n for n in dirs if not in_mount(os.path.join(rd, n)) and not excluded(os.path.join(rd, n))]
    for rel in also:
        if rel in out or excluded(rel):
            continue
        if in_mount(rel):
            out[rel] = 'mount'
            continue
        cur, bad = root, None
        for c in rel.strip('/').split('/')[:-1]:   # never follow a symlink out of the container's root
            cur += '/' + c
            try:
                if not stat.S_ISDIR(os.lstat(cur).st_mode):
                    bad = 'parent-not-dir'
                    break
            except OSError:
                bad = 'absent'
                break
        out[rel] = bad or fmeta(root, rel, upper if os.path.lexists(upper + rel) else None)
    return [('file', esc(k), v) for k, v in out.items()]


# ---------------------------------------------------------------- db
def psql(pg, db, sql):
    r = run(['docker', 'exec', '-i', pg, 'sh', '-c', 'exec psql -U "${POSTGRES_USER:-postgres}" -X -q -A -t '
             '-F "$2" -v ON_ERROR_STOP=1 -d "$1" -f -', 'sh', db, '\t'], inp=sql)
    return [l.split('\t') for l in r.stdout.splitlines() if l]


SQL_GLOBAL = f"""
select 'db', datname, pg_get_userbyid(datdba), coalesce(datacl::text,''), datallowconn from pg_database where not datistemplate order by 2;
select 'role', rolname, rolsuper, rolinherit, rolcreaterole, rolcreatedb, rolcanlogin, rolreplication, rolbypassrls from pg_roles order by 2;
select 'member', r.rolname, m.rolname, a.admin_option from pg_auth_members a join pg_roles r on r.oid=a.roleid join pg_roles m on m.oid=a.member order by 2,3;
select 'hba', md5(string_agg(concat_ws(' ', type, database::text, user_name::text, address, netmask, auth_method, options::text), E'\\n' order by line_number)) from pg_hba_file_rules;
"""
SQL_DB = f"""
select 'S', 'col', table_schema, table_name, column_name, ordinal_position, data_type, udt_name, is_nullable, coalesce(column_default,''), coalesce(character_maximum_length::text,'') from information_schema.columns where table_schema not in {PG_SYS} order by 3,4,6;
select 'S', 'con', conrelid::regclass::text, conname, pg_get_constraintdef(oid) from pg_constraint where connamespace not in (select oid from pg_namespace where nspname in {PG_SYS}) order by 3,4;
select 'S', 'idx', schemaname, tablename, indexname, indexdef from pg_indexes where schemaname not in {PG_SYS} order by 3,4,5;
select 'S', 'trg', tgrelid::regclass::text, tgname, pg_get_triggerdef(oid) from pg_trigger where not tgisinternal order by 3,4;
select 'S', 'fn', p.oid::regprocedure::text, md5(coalesce(p.prosrc,'')), p.prosecdef, pg_get_userbyid(p.proowner) from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname not in {PG_SYS} order by 3;
select 'S', 'view', schemaname, viewname, md5(definition) from pg_views where schemaname not in {PG_SYS} order by 3,4;
select 'S', 'ext', extname, extversion from pg_extension order by 3;
select 'acl', format('%I.%I',n.nspname,c.relname), c.relkind, pg_get_userbyid(c.relowner), coalesce(c.relacl::text,'') from pg_class c join pg_namespace n on n.oid=c.relnamespace where n.nspname not in {PG_SYS} and c.relkind in ('r','p','v','m','S','f') order by 2;
select 'nsp', nspname, pg_get_userbyid(nspowner), coalesce(nspacl::text,'') from pg_namespace where nspname not in {PG_SYS} and nspname not like 'pg\\_%' order by 2;
select 'seq', format('%I.%I',schemaname,sequencename), coalesce(last_value::text,'null') from pg_sequences order by 2;
select 'tbl', format('%I.%I',schemaname,tablename) from pg_tables where schemaname not in {PG_SYS} order by 2;
"""


def dbstate(project):
    pg = run(['docker', 'ps', '-q', '--filter', f'label=com.docker.compose.project={project}',
              '--filter', 'label=com.docker.compose.service=postgres']).stdout.split()
    if len(pg) != 1:
        return [('db', '_error', f'postgres containers found: {len(pg)}')]
    pg, out, dbs = pg[0], [], []
    for r in psql(pg, 'postgres', SQL_GLOBAL):
        if r[0] == 'db':
            dbs.append(r[1])
            out.append(('db', f'dbacl:{r[1]}', f'owner={r[2]} acl={r[3]} allowconn={r[4]}'))
        elif r[0] == 'role':
            out.append(('db', f'role:{r[1]}', ' '.join(f'{k}={v}' for k, v in zip(
                ('super', 'inherit', 'createrole', 'createdb', 'login', 'replication', 'bypassrls'), r[2:]))))
        elif r[0] == 'member':
            out.append(('db', f'member:{r[1]}:{r[2]}', f'admin={r[3]}'))
        elif r[0] == 'hba':
            out.append(('db', 'pg_hba', r[1]))
    out.append(('db', 'databases', ','.join(sorted(dbs))))
    for db in sorted(dbs):
        schema, tables = hashlib.sha256(), []
        for r in psql(pg, db, SQL_DB):
            if r[0] == 'S':
                schema.update('\t'.join(r).encode() + b'\n')
            elif r[0] == 'acl':
                out.append(('db', f'{db}:acl:{r[1]}', f'kind={r[2]} owner={r[3]} acl={r[4]}'))
            elif r[0] == 'nsp':
                out.append(('db', f'{db}:schema-acl:{r[1]}', f'owner={r[2]} acl={r[3]}'))
            elif r[0] == 'seq':
                out.append(('db', f'{db}:seq:{r[1]}', r[2]))
            elif r[0] == 'tbl':
                tables.append(r[1])
        out.append(('db', f'{db}:schema', schema.hexdigest()))
        if tables:
            sql = ''.join(f"select count(*), md5(coalesce(string_agg(t::text, E'\\n' order by t::text),'')) from {t} t;\n"
                          for t in tables)
            for t, r in zip(tables, psql(pg, db, sql), strict=True):
                out.append(('db', f'{db}:table:{t}', f'rows={r[0]} md5={r[1]}'))
    return out


# ---------------------------------------------------------------- s3
SCHEME = []


def mc(script, *args):
    if not SCHEME:   # the shared MinIO serves https; fall back to http (e.g. a plain test MinIO)
        for s in ('https', 'http'):
            if run(mc_cmd(s, 'mc --insecure ls x/'), check=False).returncode == 0:
                SCHEME.append(s)
                break
        else:
            raise RuntimeError('MinIO not reachable')
    return mc_cmd(SCHEME[0], script, *args)


def mc_cmd(scheme, script, *args):
    pre = f'export MC_HOST_x="{scheme}://${{MINIO_ROOT_USER}}:${{MINIO_ROOT_PASSWORD}}@localhost:9000"; exec '
    return ['docker', 'exec', MINIO, 'sh', '-c', pre + script, 'sh', *args]


def obj_md5(path):
    p = subprocess.Popen(mc('mc --insecure cat "x/$1"', path), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    h, n = hashlib.md5(), 0
    for b in iter(lambda: p.stdout.read(1 << 20), b''):
        h.update(b)
        n += len(b)
    return (h.hexdigest() if p.wait() == 0 else 'ERR'), n


def s3state(project):
    t = re.sub(r'-+', '-', re.sub(r'[^a-z0-9-]', '-', project.lower())).strip('-')
    out, objs = [], []
    for role in BUCKETS:
        b = f'{role}-{t}'
        r = run(mc('mc --insecure ls --recursive --json "x/$1"', b), check=False)
        items = [json.loads(l) for l in r.stdout.splitlines() if l.startswith('{')]
        if r.returncode or any(i.get('status') != 'success' for i in items):
            out.append(('s3', role, 'missing-or-error'))
            continue
        files_ = [i for i in items if i.get('type') == 'file']
        out.append(('s3', role, f'objects={len(files_)}'))
        objs += [(role, b, i['key'], int(i['size'])) for i in files_]
        a = run(mc('mc --insecure anonymous get --json "x/$1"', b), check=False)
        try:
            out.append(('s3', f'{role}:anonymous', json.loads(a.stdout.splitlines()[-1]).get('permission', '?')))
        except (ValueError, IndexError):
            out.append(('s3', f'{role}:anonymous', 'unknown'))
    with concurrent.futures.ThreadPoolExecutor(8) as ex:
        sums = list(ex.map(lambda o: obj_md5(f'{o[1]}/{o[2]}'), objs))
    for (role, _, key, size), (md5, n) in zip(objs, sums):
        out.append(('s3', esc(f'{role}/{key}'), f'size={size} md5={md5 if n == size else "ERR-size"}'))
    return out


# ---------------------------------------------------------------- proc, service, net
def processes(cid, pid):
    users = {}
    with open(f'/proc/{pid}/root/etc/passwd') as fh:
        for l in fh:
            f = l.split(':')
            if len(f) > 2:
                users.setdefault(f[2], f[0])
    procs = []
    for hp in run(['docker', 'top', cid, '-eo', 'pid']).stdout.split()[1:]:
        try:
            argv = [a.decode(errors='replace') for a in open(f'/proc/{hp}/cmdline', 'rb').read().split(b'\0')[:-1]]
            uid = next(l.split()[1] for l in open(f'/proc/{hp}/status') if l.startswith('Uid:'))
        except (OSError, StopIteration):
            continue   # exited meanwhile
        args = ' '.join(argv) or '[zombie]'
        for rx, rep in REDACT:
            args = rx.sub(rep, args)
        if not PROC_IGNORE.search(args):
            procs.append((hp, users.get(uid, uid), argv, args))
    return procs


def procstate(procs):
    c = collections.Counter(f'{u} {a}' for _, u, _, a in procs)
    return [('proc', esc(k), str(n)) for k, n in c.items()]


def servicestate(pid, procs):
    disk = sha_file(f'/proc/{pid}/root{SERVICE_BIN}')
    rows = []
    for hp, user, argv, _ in procs:
        if user != 'service' or not argv or os.path.basename(argv[0]) != 'model-registry':
            continue
        try:
            exe, cwd = sha_file(f"/proc/{hp}/exe", nofollow=False), os.readlink(f'/proc/{hp}/cwd')
            env = sorted(x for x in open(f'/proc/{hp}/environ', 'rb').read().split(b'\0') if x)
        except OSError:
            continue
        names = sorted({x.split(b'=', 1)[0].decode(errors='replace') for x in env})
        tdu = any(x.startswith(b'TEST_DATABASE_URL=') and len(x) > 18 for x in env)
        rows.append({'exe_sha256': exe, 'exe_matches_disk': str(exe == disk).lower(), 'user': user, 'cwd': esc(cwd),
                     'env_sha256': hashlib.sha256(b'\0'.join(
                         x for x in env if x.split(b'=', 1)[0] not in ENV_HASH_SKIP)).hexdigest(),
                     'env_names': ','.join(names),
                     'test_database_url_set': str(tdu).lower()})
    rows.sort(key=lambda r: (r['cwd'], r['exe_sha256'], r['env_sha256']))
    out = [('service', 'count', str(len(rows))), ('service', 'disk_sha256', disk)]
    return out + [('service', f'{i}.{k}', v) for i, r in enumerate(rows) for k, v in r.items()]


def addr(h, v6):
    ip, port = h.split(':')
    b = bytes.fromhex(ip)
    b = b''.join(b[i:i + 4][::-1] for i in range(0, len(b), 4))
    return f'{socket.inet_ntop(socket.AF_INET6 if v6 else socket.AF_INET, b)}:{int(port, 16)}'


def netstate(pid):
    out = []
    for tool in ('iptables', 'ip6tables'):
        r = run(['nsenter', '-t', str(pid), '-n', tool, '-S'], check=False)
        if r.returncode:
            out.append(('net', f'{tool}:_error', f'exit={r.returncode}'))
            continue
        out += [('net', esc(f'{tool}:{l}'), str(n)) for l, n in collections.Counter(r.stdout.splitlines()).items()]
    ports = collections.Counter()
    for fn in ('tcp', 'tcp6'):
        try:
            lines = open(f'/proc/{pid}/net/{fn}').read().splitlines()[1:]
        except OSError:
            continue
        for l in lines:
            f = l.split()
            if f[3] == '0A':
                a = addr(f[1], fn == 'tcp6')
                if not a.startswith(NET_IGNORE):
                    ports[f'listen:{fn}:{a}'] += 1
    return out + [('net', k, str(n)) for k, n in ports.items()]


# ---------------------------------------------------------------- capture / compare
def capture(cid, also_paths=None):
    """also_paths: iterable of paths, or of (section, key, value) lines (their `file` keys are used)."""
    also = [p[1] if isinstance(p, (tuple, list)) else p for p in (also_paths or ())
            if not isinstance(p, (tuple, list)) or p[0] == 'file']
    info = run(['docker', 'inspect', '-f', '{{.State.Pid}}\t{{index .Config.Labels "com.docker.compose.project"}}',
                cid]).stdout.strip().split('\t')
    pid, project = int(info[0]), (info[1] if len(info) > 1 and info[1] != '<no value>' else '')
    if pid <= 0:
        raise RuntimeError('container not running')
    procs = processes(cid, pid)
    steps = [('file', lambda: files(pid, also)), ('proc', lambda: procstate(procs)),
             ('service', lambda: servicestate(pid, procs)), ('net', lambda: netstate(pid)),
             ('db', lambda: dbstate(project) if project else [('db', '_error', 'no compose project')]),
             ('s3', lambda: s3state(project) if project else [('s3', '_error', 'no compose project')])]
    lines = []
    for sec, fn in steps:
        t0 = time.time()
        try:
            lines += fn()
        except Exception as e:   # messages carry no secrets: run() never includes stderr
            lines.append((sec, '_error', esc(f'{type(e).__name__}: {e}')))
        TIMINGS[sec] = round(time.time() - t0, 2)
    return sorted(set(lines))


def load(path):
    with open(path, encoding='utf-8', errors='surrogateescape') as fh:
        return [tuple(l.rstrip('\n').split('\t', 2)) for l in fh if l.strip()]


def fields(v):
    return {t.split('=', 1)[0]: t.split('=', 1)[-1] for t in v.split(' ')}


def compare(a_lines, b_lines, ignore=()):
    A, B = collections.defaultdict(dict), collections.defaultdict(dict)
    for src, dst in ((a_lines, A), (b_lines, B)):
        for s, k, v in src:
            if s not in ignore:
                dst[s][k] = v
    res = {}
    for s in sorted(set(A) | set(B)):
        a, b = A[s], B[s]
        diff = {}
        for k in sorted(set(a) & set(b)):
            if a[k] != b[k] and 'absent' in (a[k], b[k]):
                diff[k] = ['exists']
            elif a[k] != b[k]:
                fa, fb = fields(a[k]), fields(b[k])
                diff[k] = sorted(f for f in set(fa) | set(fb) if fa.get(f) != fb.get(f)) if s == 'file' else []
        res[s] = {'only_a': sorted(set(a) - set(b)), 'only_b': sorted(set(b) - set(a)), 'diff': diff}
    return {'equal': not any(r['only_a'] or r['only_b'] or r['diff'] for r in res.values()), 'sections': res}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    c = sp.add_parser('capture')
    c.add_argument('container'), c.add_argument('out'), c.add_argument('--also-paths')
    m = sp.add_parser('compare')
    m.add_argument('a'), m.add_argument('b'), m.add_argument('--ignore-section', action='append', default=[])
    args = ap.parse_args()
    if args.cmd == 'capture':
        t0 = time.time()
        lines = capture(args.container, load(args.also_paths) if args.also_paths else None)
        with open(args.out, 'w', encoding='utf-8', errors='surrogateescape') as fh:
            fh.writelines('\t'.join(l) + '\n' for l in lines)
        cnt = collections.Counter(s for s, _, _ in lines)
        errs = [s for s, k, _ in lines if k == '_error']
        print(f'wrote {len(lines)} lines to {args.out} in {time.time() - t0:.1f}s; ' +
              ', '.join(f'{s}={cnt[s]} ({TIMINGS.get(s, 0)}s)' for s in sorted(cnt)) +
              (f'; errors in: {",".join(errs)}' if errs else ''), file=sys.stderr)
        return 0
    r = compare(load(args.a), load(args.b), set(args.ignore_section))
    for s, d in r['sections'].items():
        print(f'{s}: only_a={len(d["only_a"])} only_b={len(d["only_b"])} differ={len(d["diff"])}')
        for k in d['only_a'][:30]:
            print(f'  only in A: {k}')
        for k in d['only_b'][:30]:
            print(f'  only in B: {k}')
        for k, f in list(d['diff'].items())[:30]:
            print(f'  differs:   {k}' + (f'  ({",".join(f)})' if f else ''))
    print('EQUAL' if r['equal'] else 'DIFFERENT')
    return 0 if r['equal'] else 1


if __name__ == '__main__':
    sys.exit(main())
