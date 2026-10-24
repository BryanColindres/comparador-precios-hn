"""Catálogo de Paiz Honduras (VTEX) por subcategoría -> data/paiz_precios.csv
Uso (desde la raíz del repo):  python scrapers/scrape_paiz.py
"""
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests

BASE = "https://www.paiz.com.hn"
H = {"User-Agent": "Mozilla/5.0"}
SALIDA = Path(__file__).resolve().parent.parent / "data" / "paiz_precios.csv"
# Departamentos a incluir (coincidencia parcial, sin importar mayúsculas)
INCLUIR = ("Abarrotes", "Jugos y Bebidas", "Alimentos Congelados",
           "Panadería y tortillería", "Lácteos", "Frutas y Verduras",
           "Carnes, Embutidos y Mariscos", "Limpieza", "Mascota",
           "CARNE CRUDA/CONGELADA", "FRUTAS/VERDURAS/GRANOS")


def get(url):
    for intento in range(3):
        try:
            r = requests.get(url, headers=H, timeout=30)
            if r.status_code in (200, 206):
                return r.json()
            if r.status_code == 429:
                time.sleep(5 * (intento + 1))
            else:
                return []
        except Exception:
            time.sleep(2)
    return []


def hojas(nodo, ruta="", ids=""):
    """Devuelve (ruta de ids, ruta de nombres) de las categorías sin hijos."""
    r = f"{ruta} > {nodo['name']}" if ruta else nodo["name"]
    i = f"{ids}/{nodo['id']}" if ids else str(nodo["id"])
    hijos = nodo.get("children") or []
    if not hijos:
        yield i, r
    for h in hijos:
        yield from hojas(h, r, i)


def main():
    arbol = get(f"{BASE}/api/catalog_system/pub/category/tree/3")
    if not arbol:
        raise SystemExit("No pude leer el árbol de categorías de Paiz.")
    print("Departamentos encontrados:", [n["name"] for n in arbol])

    cats = []
    for n in arbol:
        if any(k.lower() in n["name"].lower() for k in INCLUIR):
            cats += list(hojas(n))
    print(len(cats), "subcategorías a recorrer")

    filas = []
    for cid, ruta in cats:
        inicio = 0
        while inicio < 2500:
            datos = get(f"{BASE}/api/catalog_system/pub/products/search"
                        f"?fq=C:/{cid}/&_from={inicio}&_to={inicio+49}")
            if not datos:
                break
            for p in datos:
                it = p["items"][0]
                of = it["sellers"][0]["commertialOffer"]
                filas.append({
                    "fecha": date.today().isoformat(),
                    "categoria": ruta,
                    "producto": p["productName"],
                    "marca": p.get("brand"),
                    "sku": it.get("itemId"),
                    "ean": it.get("ean"),
                    "precio_lista": of.get("ListPrice"),
                    "precio_actual": of.get("Price"),
                    "disponible": of.get("AvailableQuantity", 0) > 0,
                    "url": p.get("link"),
                    "imagen_url": (it.get("images") or [{}])[0].get("imageUrl"),
                })
            inicio += 50
            time.sleep(0.8)
        print(f"{ruta}: {len(filas)} acumulados")

    df = pd.DataFrame(filas).drop_duplicates(["sku", "categoria"])
    SALIDA.parent.mkdir(exist_ok=True)
    df.to_csv(SALIDA, index=False, encoding="utf-8-sig")
    print("Listo:", len(df), "filas ->", SALIDA)


if __name__ == "__main__":
    main()
