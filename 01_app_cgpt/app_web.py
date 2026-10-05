"""app_web.py — regenera o dashboard Plotly e serve via http.server (stdlib).

Uso: python app_web.py [--port 8000] [--no-browser] [--out docs/dashboard_web.html]
"""
from __future__ import annotations
import argparse
import functools
import http.server
import threading
import webbrowser
from pathlib import Path

BASE = Path(__file__).resolve().parent


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Dashboard web (Plotly) do benchmarking")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--out", default="docs/dashboard_web.html")
    args = ap.parse_args(argv)

    import sys
    sys.path.insert(0, str(BASE))
    from scripts.web_dashboard import build_dashboard

    out = BASE / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_dashboard(), encoding="utf-8")
    url = f"http://localhost:{args.port}/{args.out}"
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(BASE))
    srv = http.server.ThreadingHTTPServer(("localhost", args.port), handler)
    print(f"servindo {out.name} em {url} (Ctrl+C para parar)")
    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
