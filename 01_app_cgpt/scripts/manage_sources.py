"""CLI CRUD das fontes publicas: python scripts/manage_sources.py <cmd> [...].

cmds: list | add ID EMPRESA \"NOME\" URL [--domains a,b] | update ID campo=valor ...
      | on|off ID | rm ID | export [dest.csv]
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.services.source_registry import SourceRegistry


def main() -> int:
    reg = SourceRegistry()
    cmd, *a = sys.argv[1:] or ["list"]
    if cmd == "list":
        for s in reg.list():
            print(f"{s['id']:16} {s['company']:14} {'ON' if s['active'] else 'OFF'} "
                  f"check={s.get('last_check_at')} dl={s.get('downloads_count')} {s['results_page']}")
    elif cmd == "add":
        sid, comp, name, url = a[0], a[1], a[2], a[3]
        kw = {}
        for tok in a[4:]:
            if tok.startswith("--domains="):
                kw["domains"] = tok.split("=", 1)[1].split(",")
        print(reg.add(sid, comp, name, url, **kw)["id"], "criada")
    elif cmd == "update":
        sid, kvs = a[0], dict(t.split("=", 1) for t in a[1:])
        print(reg.update(sid, **kvs)["id"], "atualizada")
    elif cmd in ("on", "off"):
        print(reg.set_active(a[0], cmd == "on")["id"], cmd)
    elif cmd == "rm":
        reg.remove(a[0])
        print(a[0], "removida")
    elif cmd == "export":
        dest = a[0] if a else "data/ri_registry.csv"
        print(reg.export_csv(dest), "fontes ->", dest)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
