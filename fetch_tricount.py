"""Descarga los gastos de Tricount (API de bunq) y los guarda como JSON limpio.

Uso:
  TRICOUNT_KEY=xxxx python fetch_tricount.py out.json
  TRICOUNT_KEY_SAGUNTO=xxxx python fetch_tricount.py sagunto.json --key-env=TRICOUNT_KEY_SAGUNTO
  python fetch_tricount.py out.json --from-file response_data.json   (prueba sin red)
"""
import json, os, re, sys, uuid
from datetime import datetime

CATEGORIAS = {
    "SHOPPING": "Compras 🛍️", "FOOD_AND_DRINK": "Comida 🍔", "INSURANCE": "Seguro 🛡️",
    "TRANSPORT": "Transporte 🚗", "GROCERIES": "Supermercado 🛒",
    "RENT_AND_UTILITIES": "Casa y suministros 🏠", "ENTERTAINMENT": "Entretenimiento 🎮",
    "HEALTHCARE": "Salud 🏥", "TRAVEL": "Viajes ✈️", "BALANCE": "Transferencia 💸",
    "INCOME": "Ingresos 💰", "OTHER": "Otros 📦", "UNCATEGORIZED": "Sin categoría ❓",
}


# (patrón sobre la descripción, categoría que se muestra). Añade aquí más reglas si hace falta.
REGLAS_CATEGORIA = [
    (re.compile(r"\bIBI\b", re.I), CATEGORIAS["RENT_AND_UTILITIES"]),
]


def descargar(key):
    import requests, rsa
    base = "https://api.tricount.bunq.com"
    app_id = str(uuid.uuid4())
    pub, _priv = rsa.newkeys(2048)
    headers = {
        "User-Agent": "com.bunq.tricount.android:RELEASE:14.8.2:500004156:ANDROID:13:C",
        "app-id": app_id,
        "X-Bunq-Client-Request-Id": "049bfcdf-6ae4-4cee-af7b-45da31ea85d0",
    }
    r = requests.post(f"{base}/v1/session-registry-installation", headers=headers, timeout=60, json={
        "app_installation_uuid": app_id,
        "client_public_key": pub.save_pkcs1(format="PEM").decode(),
        "device_description": "Android",
    })
    r.raise_for_status()
    items = r.json()["Response"]
    token = next(i["Token"]["token"] for i in items if "Token" in i)
    user_id = next(i["UserPerson"]["id"] for i in items if "UserPerson" in i)
    headers["X-Bunq-Client-Authentication"] = token
    r = requests.get(f"{base}/v1/user/{user_id}/registry?public_identifier_token={key}",
                     headers=headers, timeout=120)
    r.raise_for_status()
    return r.json()


def parsear(data):
    reg = data["Response"][0]["Registry"]
    miembros = [m["RegistryMembershipNonUser"]["alias"]["display_name"] for m in reg["memberships"]]
    movs = []
    for e in reg["all_registry_entry"]:
        t = e["RegistryEntry"]
        if t.get("status", "ACTIVE") != "ACTIVE":
            continue
        cat_std = t.get("category", "")
        cat = t.get("category_custom") or CATEGORIAS.get(cat_std, cat_std)
        desc = t.get("description", "")
        for patron, forzada in REGLAS_CATEGORIA:  # reglas propias: mandan sobre la categoría de Tricount
            if patron.search(desc):
                cat = forzada
                break
        movs.append({
            "d": datetime.strptime(t["date"], "%Y-%m-%d %H:%M:%S.%f").strftime("%Y-%m-%d"),
            "desc": desc,
            "paid": t["membership_owned"]["RegistryMembershipNonUser"]["alias"]["display_name"],
            "total": round(abs(float(t["amount"]["value"])), 2),
            "cur": t["amount"]["currency"],
            "cat": cat,
            "type": t["type_transaction"],
            "shares": {a["membership"]["RegistryMembershipNonUser"]["alias"]["display_name"]:
                       round(abs(float(a["amount"]["value"])), 2) for a in t["allocations"]},
        })
    movs.sort(key=lambda m: m["d"], reverse=True)
    return {"title": reg["title"], "members": miembros, "transactions": movs}


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = args[0] if args else "transactions.json"
    if "--from-file" in sys.argv:
        src = args[1]
        data = json.load(open(src, encoding="utf-8"))
    else:
        key_env = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--key-env=")), "TRICOUNT_KEY")
        key = os.environ.get(key_env)
        if not key:
            sys.exit(f"Falta la variable {key_env}")
        data = descargar(key)
    res = parsear(data)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False)
    print(f"{len(res['transactions'])} movimientos guardados en {out}")
