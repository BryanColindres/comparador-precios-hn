"""Historial de precios por producto.

Formato (data/historial.json):
  {"f": ["2026-10-24", ...],                       fechas de las corridas, en orden
   "p": {"<url relativa>": [[i, precio], ...]},    Paiz: desde la fecha f[i] el precio es "precio"
   "c": {...}}                                     La Colonia (igual). precio 0 = ya no aparece
Solo se guarda cuando el precio cambia, así el archivo crece poco.
"""
import io
import json
import subprocess
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent
RUTA = RAIZ / "data" / "historial.json"
BASE = {"p": "https://www.paiz.com.hn", "c": "https://www.lacolonia.com"}
CSV = {"p": "data/paiz_precios.csv", "c": "data/lacolonia_precios.csv"}


def vacio():
    return {"f": [], "p": {}, "c": {}}


def cargar():
    if RUTA.exists():
        h = json.loads(RUTA.read_text(encoding="utf-8"))
        h.setdefault("f", []); h.setdefault("p", {}); h.setdefault("c", {})
        return h
    return vacio()


def guardar(h):
    RUTA.parent.mkdir(exist_ok=True)
    RUTA.write_text(json.dumps(h, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def precios(df, tienda):
    """{url relativa: precio} de un DataFrame de CSV (solo precios > 0; si hay repetidos, el menor)."""
    out = {}
    base = BASE[tienda]
    for u, pr in zip(df["url"], df["precio_actual"]):
        if not isinstance(u, str) or not pr or pr <= 0:
            continue
        k = u[len(base):] if u.startswith(base) else u
        pr = round(float(pr), 2)
        if k not in out or pr < out[k]:
            out[k] = pr
    return out


def aplicar(h, tienda, fecha, actuales):
    """Agrega la corrida de `fecha` de una tienda. Seguro de repetir: no duplica la misma fecha."""
    if fecha not in h["f"]:
        h["f"].append(fecha)
        h["f"].sort()
        # si la fecha quedó en medio, los índices viejos se corren: se rehacen
        raise_if_unordered(h)
    i = h["f"].index(fecha)
    s = h[tienda]
    for k, pr in actuales.items():
        ser = s.setdefault(k, [])
        if ser and ser[-1][0] >= i:
            continue  # esta fecha ya estaba
        if not ser or ser[-1][1] != pr:
            ser.append([i, pr])
    for k, ser in s.items():
        if k not in actuales and ser and ser[-1][0] < i and ser[-1][1] != 0:
            ser.append([i, 0])
    return h


def raise_if_unordered(h):
    # Las fechas siempre se agregan al final (corridas cronológicas); si no, es un error de uso.
    if h["f"] != sorted(h["f"]):
        raise ValueError("fechas fuera de orden")


def desde_git():
    """Reconstruye el historial con los CSV de cada commit (una vez, para arrancar)."""
    def git(*a):
        return subprocess.run(["git", *a], cwd=RAIZ, capture_output=True, check=True).stdout

    h = vacio()
    por_fecha = {}  # fecha -> {tienda: df}
    for t, ruta in CSV.items():
        commits = git("log", "--reverse", "--format=%H", "--", ruta).decode().split()
        for c in commits:
            try:
                df = pd.read_csv(io.BytesIO(git("show", f"{c}:{ruta}")), encoding="utf-8-sig")
            except Exception:
                continue
            if df.empty or "fecha" not in df:
                continue
            por_fecha.setdefault(str(df["fecha"].iloc[0]), {})[t] = df  # el último commit de cada fecha gana
    for f in sorted(por_fecha):
        for t, df in por_fecha[f].items():
            aplicar(h, t, f, precios(df, t))
    return h


if __name__ == "__main__":
    h = desde_git()
    guardar(h)
    n = sum(len(v) for v in (h["p"], h["c"]))
    print("Fechas:", h["f"], "· productos con historial:", n, "· KB:", RUTA.stat().st_size // 1024)
