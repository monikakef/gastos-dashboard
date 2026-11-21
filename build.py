"""Cifra los movimientos (AES-256-GCM, clave derivada con PBKDF2) y prepara site/.

Uso: DASH_PASSWORD=... python build.py transactions.json [sagunto.json] [boda.json]
"""
import base64, json, os, shutil, sys
from datetime import datetime, timezone
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ITER = 250_000
b64 = lambda b: base64.b64encode(b).decode()

src = sys.argv[1]
password = (os.environ.get("DASH_PASSWORD") or "").strip()
if not password:
    sys.exit("Falta la variable DASH_PASSWORD")

payload = json.load(open(src, encoding="utf-8"))
if len(sys.argv) > 2 and os.path.exists(sys.argv[2]):  # Tricount secundario (Sagunto), opcional
    payload["sagunto"] = json.load(open(sys.argv[2], encoding="utf-8"))
if len(sys.argv) > 3 and os.path.exists(sys.argv[3]):  # Tricount de la boda, opcional
    payload["boda"] = json.load(open(sys.argv[3], encoding="utf-8"))
payload["generated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

salt, iv = os.urandom(16), os.urandom(12)
key = PBKDF2HMAC(hashes.SHA256(), 32, salt, ITER).derive(password.encode())
ct = AESGCM(key).encrypt(iv, json.dumps(payload, ensure_ascii=False).encode(), None)

os.makedirs("site", exist_ok=True)
with open("site/data.json", "w") as f:
    json.dump({"iter": ITER, "salt": b64(salt), "iv": b64(iv), "ct": b64(ct)}, f)
shutil.copy("index.html", "site/index.html")
for f in ("icon.svg", "icon-192.png", "icon-512.png", "apple-touch-icon.png", "manifest.webmanifest"):
    shutil.copy(f, "site/" + f)
print("site/ listo")
