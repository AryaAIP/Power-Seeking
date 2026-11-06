"""Run a command in a container through the Docker Engine API, as `docker compose exec` does, without the CLI.

Under load each `docker compose exec` costs 1–3 s just to start the docker and compose clients, and a scorer makes
dozens. power_v0.py's fast_exec= routes Inspect's sandbox exec here: the same container, command, user, environment,
working directory and stdin, with no TTY and separate stdout and stderr, exactly as `docker compose exec` runs it
from Inspect (checked: stdin a pipe that gets EOF, no TTY, nothing added to stderr). Only the transport differs.
Output is kept and decoded as Inspect's subprocess does (the last MAX bytes of each stream, errors replaced); a time
limit raises TimeoutError, which the caller retries as Inspect's compose_command does.
"""

import asyncio
import json
import struct
import urllib.parse

SOCKET = "/var/run/docker.sock"
_IDS: dict = {}


class NotStarted(RuntimeError):
    """The command never started (the container wasn't found, or the exec couldn't be created or started): it's safe
    to run it another way. Any failure after it started is raised as itself, so nothing runs twice."""


async def _request(method: str, path: str, body: dict | None = None) -> tuple[int, bytes]:
    reader, writer = await asyncio.open_unix_connection(SOCKET)
    try:
        data = json.dumps(body).encode() if body is not None else b""
        writer.write((f"{method} {path} HTTP/1.1\r\nHost: docker\r\nContent-Type: application/json\r\n"
                      f"Content-Length: {len(data)}\r\nConnection: close\r\n\r\n").encode() + data)
        await writer.drain()
        raw = await reader.read()
    finally:
        writer.close()
    head, _, rest = raw.partition(b"\r\n\r\n")
    status = int(head.split(b" ", 2)[1])
    if b"transfer-encoding: chunked" in head.lower():
        out, buf = b"", rest
        while buf:
            size_s, _, buf = buf.partition(b"\r\n")
            size = int(size_s.split(b";")[0] or b"0", 16)
            if size == 0:
                break
            out, buf = out + buf[:size], buf[size + 2:]
        rest = out
    return status, rest


async def container_id(project: str, service: str) -> str:
    key = (project, service)
    if key not in _IDS:
        filters = json.dumps({"label": [f"com.docker.compose.project={project}", f"com.docker.compose.service={service}"]})
        status, body = await _request("GET", "/containers/json?filters=" + urllib.parse.quote(filters))
        found = json.loads(body) if status == 200 else []
        if len(found) != 1:
            raise NotStarted(f"engine exec: {len(found)} containers for {project}/{service}")
        _IDS[key] = found[0]["Id"]
    return _IDS[key]


class _Tail:
    """The last `limit` bytes written (Inspect's CircularByteBuffer, for output_limit)."""

    def __init__(self, limit: int | None):
        self.limit, self.buf = limit, bytearray()

    def add(self, b: bytes) -> None:
        self.buf += b
        if self.limit is not None and len(self.buf) > self.limit:
            del self.buf[:len(self.buf) - self.limit]


async def _run(cid: str, cmd: list[str], input: bytes | None, workdir: str, env: dict | None, user: str | None,
               output_limit: int | None) -> tuple[int, str, str]:
    spec = {"AttachStdin": True, "AttachStdout": True, "AttachStderr": True, "Tty": False, "Cmd": cmd,
            "WorkingDir": workdir, "Env": [f"{k}={v}" for k, v in (env or {}).items()]}
    if user:
        spec["User"] = user
    try:
        status, body = await _request("POST", f"/containers/{cid}/exec", spec)
    except OSError as e:
        raise NotStarted(f"engine exec create: {e}") from None
    if status != 201:
        raise NotStarted(f"engine exec create: HTTP {status}")
    eid = json.loads(body)["Id"]
    try:
        reader, writer = await asyncio.open_unix_connection(SOCKET)
    except OSError as e:
        raise NotStarted(f"engine exec connect: {e}") from None
    out, err = _Tail(output_limit), _Tail(output_limit)
    try:
        start = json.dumps({"Detach": False, "Tty": False}).encode()
        writer.write((f"POST /exec/{eid}/start HTTP/1.1\r\nHost: docker\r\nContent-Type: application/json\r\n"
                      f"Connection: Upgrade\r\nUpgrade: tcp\r\nContent-Length: {len(start)}\r\n\r\n").encode() + start)
        await writer.drain()
        head = await reader.readuntil(b"\r\n\r\n")
        code = int(head.split(b" ", 2)[1])
        if code not in (101, 200):  # the daemon refused to start it
            raise NotStarted(f"engine exec start: HTTP {code}")
        if input:
            writer.write(input)
            await writer.drain()
        writer.write_eof()  # the command's stdin reaches EOF, as with `docker compose exec` from a non-tty
        while True:
            try:
                hdr = await reader.readexactly(8)
            except asyncio.IncompleteReadError:
                break
            stream, size = hdr[0], struct.unpack(">I", hdr[4:])[0]
            payload = await reader.readexactly(size)
            (err if stream == 2 else out).add(payload)
    finally:
        writer.close()
    for _ in range(50):  # the exit code is set a moment after the stream closes
        status, body = await _request("GET", f"/exec/{eid}/json")
        info = json.loads(body)
        if not info.get("Running"):
            break
        await asyncio.sleep(0.05)
    return int(info.get("ExitCode") or 0), bytes(out.buf).decode(errors="replace"), bytes(err.buf).decode(errors="replace")


async def exec_with_timeout(cid: str, cmd: list[str], input: str | bytes | None, workdir: str, env: dict | None,
                            user: str | None, timeout: int | None, timeout_retry: bool,
                            output_limit: int | None, compose_args: list | None = None) -> tuple[int, str, str]:
    """As Inspect's compose_command: with a time limit, a timed-out attempt is retried up to twice, at the limit and then
    at min(limit, 60) // retries; then TimeoutError, with compose_command's own message (compose_args: the arguments it
    would have had, from "exec" on)."""
    data = input.encode() if isinstance(input, str) else input
    if timeout is None:
        return await _run(cid, cmd, data, workdir, env, user, output_limit)
    retries = 0
    while True:
        limit = max(timeout if retries == 0 else (min(timeout, 60) // retries), 1)
        try:
            return await asyncio.wait_for(_run(cid, cmd, data, workdir, env, user, output_limit), limit)
        except (TimeoutError, asyncio.TimeoutError):
            retries += 1
            if not (timeout_retry and retries <= 2):
                raise TimeoutError(f"Docker compose command '{compose_args}' timed out after {timeout} seconds") from None
