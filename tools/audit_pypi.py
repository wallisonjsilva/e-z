"""Consulta somente nomes/versões públicos; não resolve nem executa pacotes."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import tomllib
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def query(package):
    name, version = package
    url = f"https://pypi.org/pypi/{name}/{version}/json"
    try:
        with urlopen(Request(url, headers={"User-Agent": "e-z-dependency-review/1"}), timeout=20) as response:
            value = json.load(response)
        return {"name": name, "version": version, "source": url, "vulnerabilities": value.get("vulnerabilities", []), "complete": True}
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
        # Não imprimir exceções que possam conter detalhes do ambiente.
        return {"name": name, "version": version, "complete": False, "error": type(error).__name__}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tool", action="append", default=[], help="Pacote público extra, no formato nome==versão")
    args = parser.parse_args()
    path = Path("uv.lock")
    lock = tomllib.loads(path.read_text())
    packages = {(p["name"], p["version"]) for p in lock["package"] if "registry" in p["source"]}
    for item in args.tool:
        name, version = item.split("==", 1)
        if not name or not version or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_." for c in name + version):
            parser.error("Use apenas nome e versão públicos simples.")
        packages.add((name, version))
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(query, sorted(packages)))
    active = sum(len([v for v in p.get("vulnerabilities", []) if not v.get("withdrawn")]) for p in results)
    report = {"queried_at_utc": datetime.now(timezone.utc).isoformat(), "lock_sha256": sha256(path.read_bytes()).hexdigest(),
              "summary": {"packages": len(results), "complete": all(p["complete"] for p in results), "active_advisories": active},
              "packages": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report["summary"]))
    return 2 if not report["summary"]["complete"] else int(active > 0)


if __name__ == "__main__":
    raise SystemExit(main())
