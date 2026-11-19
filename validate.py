#!/usr/bin/env python3
"""POST fixture(s) to an OpenAI-compatible /v1/chat/completions and check for tool-name leaks.

Usage:
  STRATA_URL=http://127.0.0.1:8080 STRATA_KEY=… python validate.py fixtures/taskcreate_claude_code.json

Exit 0 = no undeclared tool name in tool_calls or as call markup in content.
Exit 1 = leak (or HTTP/usage error).

Optional: STRATA_METRICS=1 also prints /metrics totals.tool_markup_retries before/after
(when the server exposes that field — Strata does).
"""
from __future__ import annotations

import json, os, re, sys, urllib.error, urllib.request

MARK = re.compile(
    r'(?m)^[ \t]*(?:<tool_call>\s*)?(?:<function=([A-Za-z_0-9.\-]+)>|<invoke name="([A-Za-z_0-9.\-]+)")'
)


def declared(body: dict) -> set[str]:
    out = []
    for t in body.get("tools") or []:
        out.append((t.get("function") or {}).get("name") or t.get("name"))
    return {n for n in out if n}


def http(url: str, key: str, path: str, body=None, timeout=2400):
    req = urllib.request.Request(
        url.rstrip("/") + path,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def retries(url: str, key: str):
    try:
        d = http(url, key, "/metrics", timeout=30)
        return (d.get("totals") or {}).get("tool_markup_retries")
    except Exception as e:  # noqa: BLE001
        return f"unavailable ({e!r:.80})"


def check(url: str, key: str, path: str, want_metrics: bool) -> int:
    body = json.loads(open(path, encoding="utf-8").read())
    body["stream"] = False
    body.pop("stream_options", None)
    decl = declared(body)
    if not decl:
        print(f"{path}: no tools in fixture", file=sys.stderr)
        return 1
    r0 = retries(url, key) if want_metrics else None
    try:
        r = http(url, key, "/v1/chat/completions", body)
    except urllib.error.HTTPError as e:
        print(f"{path}: HTTP {e.code} {e.read()[:300]!r}", file=sys.stderr)
        return 1
    ch = r["choices"][0]
    msg = ch["message"]
    calls = [(c.get("function") or {}).get("name") for c in (msg.get("tool_calls") or [])]
    content = msg.get("content") or ""
    leaked = [a or b for a, b in MARK.findall(content)]
    bad = [n for n in calls + leaked if n and n not in decl]
    r1 = retries(url, key) if want_metrics else None
    print(f"{path}: finish={ch.get('finish_reason')} calls={calls} leaked_markup={leaked} bad={bad}")
    if want_metrics:
        print(f"  tool_markup_retries: before={r0} after={r1}")
    if bad:
        print("FAIL: undeclared tool name(s)", file=sys.stderr)
        return 1
    print("OK")
    return 0


def main() -> int:
    url = os.environ.get("STRATA_URL") or os.environ.get("OPENAI_BASE_URL") or ""
    key = os.environ.get("STRATA_KEY") or os.environ.get("OPENAI_API_KEY") or ""
    if not url or not key:
        print("Set STRATA_URL (or OPENAI_BASE_URL) and STRATA_KEY (or OPENAI_API_KEY)", file=sys.stderr)
        return 2
    if "/v1" in url.rstrip("/"):
        # allow either base or …/v1
        url = url.rstrip("/").removesuffix("/v1")
    paths = sys.argv[1:] or ["fixtures/taskcreate_claude_code.json"]
    want = os.environ.get("STRATA_METRICS", "").strip() in ("1", "true", "yes")
    rc = 0
    for p in paths:
        rc = max(rc, check(url, key, p, want))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
