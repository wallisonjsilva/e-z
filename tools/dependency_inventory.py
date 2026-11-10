"""Inventário local sem caminhos pessoais nem conteúdo de documentos."""

import argparse
import ast
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import distributions
import json
from pathlib import Path
import platform
import tomllib


def inventory():
    lock_path = Path("uv.lock")
    lock = tomllib.loads(lock_path.read_text())
    project = tomllib.loads(Path("pyproject.toml").read_text())
    installed = {}
    for distribution in distributions():
        name = distribution.metadata["Name"].lower().replace("_", "-")
        installed[name] = {"name": name, "version": distribution.version,
                           "license": distribution.metadata.get("License-Expression") or distribution.metadata.get("License")}
    modules = set()
    for path in Path("src/true_screen").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("PySide6."):
                modules.add(node.module)
    from PySide6.QtCore import qVersion
    return {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(), "system": platform.system(), "machine": platform.machine(),
        "libc": platform.libc_ver(), "qt": qVersion(),
        "lock_sha256": sha256(lock_path.read_bytes()).hexdigest(),
        "build_requires": project["build-system"]["requires"],
        "application_qt_imports": sorted(modules),
        "installed": sorted(installed.values(), key=lambda package: package["name"]),
        "locked": [{"name": p["name"], "version": p["version"], "source": p["source"]}
                   for p in lock["package"]],
        "notes": ["Inventário de pacotes, não SBOM nativo completo.", "Entradas duplicadas de lib/lib64 foram normalizadas."],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(inventory(), indent=2, ensure_ascii=False) + "\n")
