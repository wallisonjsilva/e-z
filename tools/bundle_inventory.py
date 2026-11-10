"""Manifesto de integridade/ELF do candidato local; não é scanner de CVEs."""

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess


def inspect_bundle(root):
    if not root.is_dir() or not (root / "e-z").is_file():
        raise ValueError("Diretório de candidato e-z inválido.")
    files, links, broken = [], [], []
    bundled_names, needed, versions = set(), set(), set()
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            import os
            links.append({"path": relative, "target": os.readlink(path)})
            if not path.exists():
                broken.append(relative)
            bundled_names.add(path.name)
            continue
        if not path.is_file():
            continue
        digest = sha256()
        with path.open("rb") as file:
            magic = file.read(4)
            file.seek(0)
            for block in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(block)
        record = {"path": relative, "bytes": path.stat().st_size, "sha256": digest.hexdigest()}
        bundled_names.add(path.name)
        if magic == b"\x7fELF":
            dynamic = subprocess.run(["readelf", "-d", str(path)], check=True, text=True, capture_output=True).stdout
            version_data = subprocess.run(["readelf", "--version-info", str(path)], check=True, text=True, capture_output=True).stdout
            record["needed"] = sorted(set(re.findall(r'\(NEEDED\).*\[(.*?)\]', dynamic)))
            record["glibc_versions"] = sorted(set(re.findall(r'GLIBC_(\d+(?:\.\d+)+)', version_data)))
            needed.update(record["needed"])
            versions.update(record["glibc_versions"])
        files.append(record)
    return {"captured_at_utc": datetime.now(timezone.utc).isoformat(), "files": files, "symlinks": links,
            "broken_links": broken, "total_regular_bytes": sum(f["bytes"] for f in files),
            "native_qt_libraries": sorted({Path(f["path"]).name for f in files if Path(f["path"]).name.startswith("libQt6")}),
            "external_sonames": sorted(needed - bundled_names),
            "unresolved_qt_sonames": sorted(n for n in needed - bundled_names if n.startswith("libQt6")),
            "max_glibc_symbol_version": max(versions, key=lambda v: tuple(map(int, v.split('.')))) if versions else None,
            "notes": ["Dependências externas por SONAME, sem validação de disponibilidade ou CVEs do sistema.",
                      "Hashes identificam estes arquivos; não constituem assinatura/autenticidade."]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = inspect_bundle(args.bundle)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: report[key] for key in ("total_regular_bytes", "max_glibc_symbol_version", "native_qt_libraries", "external_sonames", "broken_links")}))
    raise SystemExit(bool(report["broken_links"] or report["unresolved_qt_sonames"]))
