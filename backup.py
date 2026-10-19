"""Online-consistent SQLite backup. Store output on an independent encrypted device."""

import argparse
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

parser = argparse.ArgumentParser(
    description="Copia consistente de la base de datos Factora"
)
parser.add_argument("--database", default=os.getenv("DATABASE_PATH", "data/factora.db"))
parser.add_argument("--output", default=None)
args = parser.parse_args()
source = Path(args.database).resolve()
if not source.is_file():
    parser.error("La base de datos de origen no existe.")
output = Path(
    args.output
    or (
        "backups/factora-"
        + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        + ".db"
    )
).resolve()
if output.exists() or source == output:
    parser.error("El destino ya existe. Elige un archivo nuevo.")
output.parent.mkdir(parents=True, exist_ok=True)
with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as original:
    with sqlite3.connect(output) as backup:
        original.backup(backup)
        assert backup.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
os.chmod(output, 0o600)
print(f"Copia verificada: {output}")
