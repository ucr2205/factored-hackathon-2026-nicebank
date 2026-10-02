#!/usr/bin/env python3
"""Adapta infra/keycloak/latam-bank-realm.json al dominio público (solo librería estándar).

Cambia las URLs de redirección/orígenes del cliente "web" de localhost al dominio del frontend.
Con --sin-pruebas además quita el cliente "eval-harness" (direct grants) y los usuarios de carga
carga01..carga20, como recomienda docs/production_gap.md.

IMPORTANTE: Keycloak solo importa el realm la PRIMERA vez (si no existe en su BD). Ejecutar esto antes
del primer arranque; si ya arrancó, cambiar las URLs en la consola (Clients > web) o borrar el realm.

Uso:
  python3 adaptar_realm.py /opt/servicios-apis/EVON/nicebank/infra/keycloak/latam-bank-realm.json \
      --front https://hackathon.evon.solutions [--sin-pruebas]
"""
import argparse
import json
import shutil
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("realm", type=Path)
ap.add_argument("--front", required=True, help="origen público del frontend, sin barra final")
ap.add_argument("--mantener-localhost", action="store_true", help="conserva también las URLs localhost")
ap.add_argument("--sin-pruebas", action="store_true", help="quita eval-harness y usuarios cargaNN")
a = ap.parse_args()

front = a.front.rstrip("/")
backup = a.realm.with_suffix(".json.orig")
if not backup.exists():
    shutil.copy2(a.realm, backup)
realm = json.loads(a.realm.read_text(encoding="utf-8"))

for c in realm["clients"]:
    if c["clientId"] != "web":
        continue
    keep = [u for u in c.get("redirectUris", []) if a.mantener_localhost]
    c["redirectUris"] = [f"{front}/*"] + keep
    c["webOrigins"] = [front] + ([o for o in c.get("webOrigins", [])] if a.mantener_localhost else [])
    c.setdefault("attributes", {})["post.logout.redirect.uris"] = "##".join(c["redirectUris"])
    c["rootUrl"] = front

if a.sin_pruebas:
    realm["clients"] = [c for c in realm["clients"] if c["clientId"] != "eval-harness"]
    realm["users"] = [u for u in realm["users"] if not u["username"].startswith("carga")]

a.realm.write_text(json.dumps(realm, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
web = next(c for c in realm["clients"] if c["clientId"] == "web")
print("redirectUris:", web["redirectUris"])
print("webOrigins:  ", web["webOrigins"])
print("clientes:    ", [c["clientId"] for c in realm["clients"]])
print("usuarios:    ", len(realm["users"]), "| respaldo en", backup)
