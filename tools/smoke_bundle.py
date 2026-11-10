"""Verifica somente inicialização offscreen do executável congelado Linux."""

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("executable", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    executable = args.executable.resolve(strict=True)
    environment = os.environ.copy()
    for key in ("PYTHONPATH", "PYTHONHOME", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH", "LD_LIBRARY_PATH", "LD_PRELOAD"):
        environment.pop(key, None)
    environment["QT_QPA_PLATFORM"] = "offscreen"
    with tempfile.TemporaryDirectory(prefix="true-screen-smoke-") as directory:
        with tempfile.TemporaryFile() as log:
            process = subprocess.Popen([str(executable)], cwd=directory, env=environment,
                                       stdout=log, stderr=log)
            try:
                process.wait(timeout=3)
                alive = False
            except subprocess.TimeoutExpired:
                alive = True
            finally:
                if process.poll() is None:
                    process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            # Não copiar mensagens externas com caminhos/dados do ambiente.
            report = {"captured_at_utc": datetime.now(timezone.utc).isoformat(),
                      "executable_sha256": sha256(executable.read_bytes()).hexdigest(),
                      "platform": "offscreen", "alive_after_3_seconds": alive,
                      "returncode_after_termination": process.returncode,
                      "notes": ["Diretório temporário fora do projeto; variáveis de busca Python/Qt removidas.",
                                "Encerramento por sinal; não valida fechamento pela UI nem funções ou sessão nativa."]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False))
    return int(not alive)


if __name__ == "__main__":
    raise SystemExit(main())
