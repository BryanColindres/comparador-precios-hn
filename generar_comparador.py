"""Genera docs/index.html (comparador móvil Paiz vs La Colonia) desde los CSV de data/.

Uso (desde la raíz del repo):
    python generar_comparador.py
    python generar_comparador.py paiz.csv lacolonia.csv      # CSV en otra ruta

Cómo se relacionan los productos entre tiendas:
  1. Código de barras (EAN): mismo producto exacto.
  2. Coincidencia probable: misma marca, mismo tamaño (±2 %) y nombre muy parecido.
  3. En la página, "Similares" busca alternativas del mismo tipo y tamaño en la otra tienda.
La lista de productos básicos (LISTA) se puede editar más abajo.
"""
import bisect
import json
import math
import re
import sys
import unicodedata
import warnings
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore", message="This pattern is interpreted")

RAIZ = Path(__file__).resolve().parent
CSV_PAIZ = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "data" / "paiz_precios.csv"
CSV_COL = Path(sys.argv[2]) if len(sys.argv) > 2 else RAIZ / "data" / "lacolonia_precios.csv"
SALIDA = RAIZ / "docs"
PLANTILLA = RAIZ / "plantilla.html"
for f in (CSV_PAIZ, CSV_COL, PLANTILLA):
    if not f.exists():
        sys.exit(f"No encuentro {f}. Corre primero los scrapers (carpeta scrapers/).")


# ───────────────────────── Normalización de texto ─────────────────────────
def norm(s):
    s = unicodedata.normalize("NFD", str(s).lower())
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn")


def stem(t):
    """huevos -> huevo, papas -> papa (singular simple)."""
    return t[:-1] if len(t) > 3 and t.endswith("s") and not t.endswith("ss") else t


STOP = set("""de del la el los las con sin x un una y en por para al a o e pack paquete bolsa bandeja caja
frasco botella lata unidad unidades und unds uds u gr g kg kgs lb lbs libra libras oz ml l lt lts litro litros
aprox aproximadamente precio indicado venta granel fresco fresca""".split())
GENERICAS = {"sin marca", "generico", "no aplica", "na", ""}


def toks(s):
    out = []
    for t in re.findall(r"[a-z0-9]+", norm(s)):
        out += ["great", "value"] if t == "gv" else [t]
    return out


def nucleo(nombre, marca):
    """Palabras significativas del nombre (sin marca, tamaños ni relleno)."""
    bt = {stem(t) for t in toks(marca)}
    return frozenset(w for w in (stem(t) for t in toks(nombre))
                     if w not in STOP and w not in bt and not re.search(r"\d", w))


# ───────────────────────── Tamaños y precio por unidad ─────────────────────
W = {"kg": 2.20462, "kgs": 2.20462, "g": 1 / 453.592, "gr": 1 / 453.592, "grs": 1 / 453.592,
     "lb": 1, "lbs": 1, "libra": 1, "libras": 1, "oz": 1 / 16}
V = {"ml": 1 / 1000, "l": 1, "lt": 1, "lts": 1, "litro": 1, "litros": 1}
U = ("u", "ud", "uds", "und", "unid", "unidad", "unidades", "un", "unds")
UNIT_RE = r"(kgs?|grs?|g|lbs?|libras?|oz|ml|lts?|litros?|l|unidades|unidad|unids?|unds?|und|uds?|un|u)"


def unidad(nombre, precio):
    """(precio por unidad, 'lb'|'L'|'u', cantidad total en lb/L/unidades) o (None, None, None)."""
    n = norm(nombre)
    if re.search(r"por libra|por lb|x lb\b|/lb\b", n):
        return precio, "lb", 1.0
    # "…Libra - 2 a 4 Unidades aprox." = precio por libra (salvo que indique "2 Lb" de peso)
    if re.search(r"\blibra\b", n) and not re.search(r"\d\s*(lbs?|libras?)\b", n):
        return precio, "lb", 1.0
    mult = 1
    fr = re.search(r"(\d+)\s*/\s*(\d+)\s*" + UNIT_RE + r"\b", n)  # "1/2 Lb"
    m = re.search(r"(\d+)\s*(?:x|pack de|pk)\s*(\d+(?:[.,]\d+)?)\s*" + UNIT_RE + r"\b", n)
    if fr and int(fr.group(2)) > 0:
        cant, u = int(fr.group(1)) / int(fr.group(2)), fr.group(3)
    elif m:
        mult, cant, u = int(m.group(1)), float(m.group(2).replace(",", ".")), m.group(3)
    else:
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*" + UNIT_RE + r"\b", n)
        if not m:
            # "X Unidad", "Venta Por Unidad", "... Un" al final = precio de 1 unidad
            if re.search(r"(\bx|\bpor)\s*unidad\b|\bunidad$|\bun$", n):
                return precio, "u", 1.0
            return None, None, None
        cant, u = float(m.group(1).replace(",", ".")), m.group(2)
    if cant <= 0:
        return None, None, None
    if u in W:
        tot, et = cant * mult * W[u], "lb"
    elif u in V:
        tot, et = cant * mult * V[u], "L"
    elif u in U:
        tot, et = cant * mult, "u"
    else:
        return None, None, None
    return (precio / tot, et, tot) if tot > 0 else (None, None, None)


def canonico(et, tot):
    """Cantidad en gramos, mililitros o unidades (para comparar tamaños)."""
    return {"lb": tot * 453.592, "L": tot * 1000}.get(et, tot) if et else None


def tam(et, q):
    if not et or not q:
        return ""
    if et == "lb":
        if abs(q - 453.592) < 2:
            return "1 lb"
        return f"{q/1000:.3g} kg" if q >= 1000 else f"{q:.0f} g"
    if et == "L":
        return f"{q/1000:.3g} L" if q >= 1000 else f"{q:.0f} ml"
    return f"{q:g} u"


# ───────────────────────── Carga de CSV ─────────────────────────
def cargar(ruta):
    df = pd.read_csv(ruta, dtype={"ean": str, "sku": str})
    # Paiz usa 13 dígitos (con 0 adelante) y La Colonia a veces 12: se igualan quitando
    # ceros a la izquierda. Códigos de menos de 8 dígitos (PLU internos) no se cruzan.
    df["ean"] = df["ean"].fillna("").str.strip().str.lstrip("0")
    df.loc[df["ean"].str.len() < 8, "ean"] = ""
    df["marca"] = df["marca"].fillna("")
    df = df[df["precio_actual"].fillna(0) > 0].copy()
    df = df.sort_values("precio_actual").drop_duplicates(["ean", "sku"])
    res = [unidad(r, float(pr)) for r, pr in zip(df["producto"], df["precio_actual"])]
    df["up"] = [x[0] for x in res]
    df["ul"] = [x[1] for x in res]
    df["qty"] = [canonico(x[1], x[2]) for x in res]
    df["nn"] = df["producto"].map(norm)
    df["cn"] = df["categoria"].map(norm)
    df["core"] = [nucleo(a, b) for a, b in zip(df["producto"], df["marca"])]
    return df


p, c = cargar(CSV_PAIZ), cargar(CSV_COL)
fecha_p = str(pd.read_csv(CSV_PAIZ, usecols=["fecha"])["fecha"].iloc[0])
fecha_c = str(pd.read_csv(CSV_COL, usecols=["fecha"])["fecha"].iloc[0])


def prefijo_img(df):
    imgs = [x for x in df["imagen_url"].dropna() if isinstance(x, str)]
    pre = __import__("os").path.commonprefix(imgs) if imgs else ""
    return pre[: pre.rfind("/") + 1]


PFX = {"p": {"u": "https://www.paiz.com.hn", "i": prefijo_img(p)},
       "c": {"u": "https://www.lacolonia.com", "i": prefijo_img(c)}}


def rel(valor, prefijo):
    v = valor if isinstance(valor, str) else ""
    return v[len(prefijo):] if prefijo and v.startswith(prefijo) else v


# ───────────────────────── Lista de productos básicos ─────────────────────────
NO_PROC = (r"salsa|pasta de|jugo|ketchup|kechup|enlatad|pure|sopa|encurtid|snack|chips|papitas|frita|congelad|"
           r"mermelada|dulce de|deshidratad|polvo|saborizad|sabor a|galleta|cereal|yogurt|helado|vinagre|aderezo|"
           r"mayonesa|condimento")
VERD = r"frutas y verduras"


def it(g, n, inc, exc="", u="lb", cat=None, qty=None):
    """g=grupo, n=nombre, inc=regex que debe aparecer, exc=regex que NO debe aparecer,
    u=unidad (lb|L|u), cat=regex de la categoría de la tienda, qty=tamaño exacto del empaque."""
    return {"g": g, "n": n, "inc": inc, "exc": NO_PROC + (("|" + exc) if exc else ""),
            "u": u, "cat": cat, "qty": qty}


LISTA = [
    it("Verduras", "Tomate", r"\btomate", "secos", cat=VERD),
    it("Verduras", "Cebolla", r"\bcebolla", "polvo|morada", cat=VERD),
    it("Verduras", "Papa", r"\bpapa\b|\bpapas\b", cat=VERD),
    it("Verduras", "Chile dulce", r"chile (dulce|pimiento)|pimiento", cat=VERD),
    it("Verduras", "Zanahoria", r"zanahoria", cat=VERD),
    it("Verduras", "Repollo", r"repollo", cat=VERD),
    it("Verduras", "Pepino", r"pepino", cat=VERD),
    it("Verduras", "Lechuga", r"lechuga", cat=VERD),
    it("Verduras", "Ajo", r"\bajo\b|\bajos\b", "molido|salsa", cat=VERD),
    it("Verduras", "Güisquil", r"guisquil|chayote", cat=VERD),
    it("Verduras", "Yuca", r"\byuca", cat=VERD),
    it("Verduras", "Aguacate", r"aguacate", "aceite", cat=VERD),
    it("Frutas", "Plátano", r"platano", "tostone|maduro frito|precocid|tajada", cat=VERD),
    it("Frutas", "Banano", r"banano|guineo", cat=VERD),
    it("Frutas", "Naranja", r"\bnaranja", cat=VERD),
    it("Frutas", "Limón", r"\blimon", "albahaca|hierba|menta|te ", cat=VERD),
    it("Frutas", "Manzana", r"\bmanzana", cat=VERD),
    it("Frutas", "Sandía", r"sandia", cat=VERD),
    it("Frutas", "Piña", r"\bpina\b", cat=VERD),
    it("Frutas", "Mango", r"\bmango", cat=VERD),
    it("Frutas", "Papaya", r"papaya", cat=VERD),
    it("Carnes", "Pechuga de pollo", r"pechuga", "empanizad|nugget|pavo|jamon", cat=r"carnes|pollo"),
    it("Carnes", "Muslo de pollo", r"muslo|encuentro", "empanizad", cat=r"carnes|pollo"),
    it("Carnes", "Pollo entero", r"pollo entero|pollo fresco",
       "menudo|fajita|pechuga|muslo|pierna|alas|molid|marinad|pavo|encuentro|filete|nugget|empaniz|caldo|hueso",
       cat=r"carnes|pollo"),
    it("Carnes", "Carne molida de res", r"molida|molido", "cerdo|pollo|pavo", cat=r"carnes|\bres\b"),
    it("Carnes", "Carne para asar (res)", r"\basar\b", "cerdo|pollo", cat=r"carnes|\bres\b"),
    it("Carnes", "Costilla de cerdo", r"costilla", r"res\b", cat=r"carnes|cerdo"),
    it("Carnes", "Chuleta de cerdo", r"chuleta", cat=r"carnes|cerdo"),
    it("Carnes", "Chorizo", r"chorizo", "pack|kimby", cat=r"embutidos"),
    it("Carnes", "Tocino", r"tocino", cat=r"embutidos|tocino"),
    it("Carnes", "Tilapia / pescado", r"tilapia|pescado", "enlatad|atun|sardina|cabeza|gato|perro",
       cat=r"pescados|mariscos"),
    it("Granos y despensa", "Frijol rojo", r"frijol", "molido|refrito|enlatad|negro|blanco|instantane",
       cat=r"arroz, frijol|frijoles"),
    it("Granos y despensa", "Arroz", r"\barroz\b", "con leche|pollo", cat=r"arroz"),
    it("Granos y despensa", "Azúcar", r"azucar", "sin azucar|splenda|stevia", cat=r"azucar|endulzante"),
    it("Granos y despensa", "Sal", r"\bsal\b", "aderezo|con ajo|pimienta|ajo|cebolla|adobo|condimento",
       cat=r"sal y condimentos|sopas, cremas y condimentos|especias"),
    it("Granos y despensa", "Harina de maíz", r"harina.*maiz|maiz.*harina|masa de maiz|maseca", cat=r"harina"),
    it("Granos y despensa", "Pasta / espagueti", r"espagueti|spaghetti|fideo|macarron", "salsa|instantane",
       cat=r"pastas"),
    it("Granos y despensa", "Café molido", r"cafe", "capuchino|instantaneo|soluble|3 en 1|crema|listo|te |betun",
       cat=r"cafe"),
    it("Granos y despensa", "Aceite vegetal", r"aceite", "oliva|aguacate|coco|spray|motor|manteca", u="L",
       cat=r"aceites"),
    it("Lácteos y huevos", "Huevo · 30 unidades", r"\bhuevo", "codorniz|liquido|pascua|chocolate", u="u",
       cat=r"huevo", qty=30),
    it("Lácteos y huevos", "Huevo · 15 unidades", r"\bhuevo", "codorniz|liquido|pascua|chocolate", u="u",
       cat=r"huevo", qty=15),
    it("Lácteos y huevos", "Huevo · 20 unidades", r"\bhuevo", "codorniz|liquido|pascua|chocolate", u="u",
       cat=r"huevo", qty=20),
    it("Lácteos y huevos", "Leche líquida", r"\bleche\b",
       "polvo|condensada|evaporada|coco|chocolate|fresa|soya|almendra|avena|saborizada|malteada|bebida de",
       u="L", cat=r"leche entera|leche semi|deslactosada|leches liquidas"),
    it("Lácteos y huevos", "Queso", r"\bqueso", "rallado|crema|untable", cat=r"queso"),
    it("Lácteos y huevos", "Mantequilla", r"mantequilla", "mani|cacahuate|avellana|margarina",
       cat=r"mantequilla"),
    it("Panadería", "Tortillas", r"tortilla", "chips|tostada|totopo|nacho", u="u", cat=r"tortill"),
]


def mejor(df, e, ul, minimo=0):
    m = (df["ul"] == ul) & df["nn"].str.contains(e["inc"], regex=True) \
        & ~df["nn"].str.contains(e["exc"], regex=True)
    if e["cat"]:
        m &= df["cn"].str.contains(e["cat"], regex=True)
    if e["qty"]:
        m &= (df["qty"] - e["qty"]).abs() <= 0.01 * e["qty"]
    d = df[m]
    if d.empty:
        return None
    med = d["up"].median()
    d = d[(d["up"] >= 0.15 * med) & (d["up"] >= minimo)]  # descarta errores de tamaño en el nombre
    if d.empty:
        return None
    r = d.sort_values("up").iloc[0]
    # [precio por unidad más bajo, producto, precio del empaque, precio típico (mediana), # de productos,
    #  tamaño, imagen, link]
    return [round(float(r["up"]), 2), r["producto"], round(float(r["precio_actual"]), 2),
            round(float(d["up"].median()), 2), int(len(d)), tam(r["ul"], r["qty"]),
            r["imagen_url"] if isinstance(r["imagen_url"], str) else "", r["url"]]


def por_tienda(df, tienda, e):
    prod = e["g"] in ("Verduras", "Frutas")
    out = {}
    r = mejor(df, e, e["u"], minimo=3 if prod and e["u"] == "lb" else 0)  # fruta/verdura < L.3/lb = error
    if r:
        out[e["u"]] = r
    if prod and e["u"] == "lb":
        r2 = mejor(df, e, "u")  # muchas frutas/verduras se venden por unidad
        if r2:
            out["u"] = r2
    for v in out.values():
        v[6], v[7] = rel(v[6], PFX[tienda]["i"]), rel(v[7], PFX[tienda]["u"])
    return out


lista = [{"g": e["g"], "n": e["n"], "u": e["u"], "p": por_tienda(p, "p", e), "c": por_tienda(c, "c", e)}
         for e in LISTA]
print("Lista fija: Paiz", sum(1 for x in lista if x["p"]), "· La Colonia", sum(1 for x in lista if x["c"]),
      "de", len(lista))
print("Sin resultado:", [x["n"] for x in lista if not x["p"] and not x["c"]])


# ───────────────────────── Relación entre tiendas ─────────────────────────
def registro(r, tienda):
    return {"t": tienda, "id": f'{tienda}{r["sku"]}', "ean": r["ean"], "nombre": r["producto"],
            "marca": r["marca"], "precio": float(r["precio_actual"]),
            "lista": float(r["precio_lista"]) if pd.notna(r["precio_lista"]) else 0.0,
            "up": r["up"] if pd.notna(r["up"]) else None,
            "ul": r["ul"] if isinstance(r["ul"], str) else None,
            "qty": r["qty"] if pd.notna(r["qty"]) else None,
            "url": r["url"], "img": r["imagen_url"], "core": r["core"],
            "bt": frozenset(stem(t) for t in toks(r["marca"]) if stem(t) not in STOP)}


def lado(r):
    t = r["t"]
    return [round(r["precio"], 2), round(r["lista"], 2), round(r["up"], 2) if r["up"] else 0, r["ul"] or "",
            round(r["qty"], 1) if r["qty"] else 0, rel(r["url"], PFX[t]["u"]),
            rel(r["img"], PFX[t]["i"]), r["nombre"], " ".join(sorted(r["core"])), tam(r["ul"], r["qty"])]


P = [registro(r, "p") for r in p.to_dict("records")]
C = [registro(r, "c") for r in c.to_dict("records")]

# 1) Un solo registro por código de barras (el más barato) en cada tienda
def unicos(regs):
    vistos, out = {}, []
    for r in regs:  # ya vienen ordenados por precio ascendente
        if r["ean"]:
            if r["ean"] in vistos:
                continue
            vistos[r["ean"]] = r
        out.append(r)
    return out, vistos


P, pe = unicos(P)
C, ce = unicos(C)

items, usados_p, usados_c = [], set(), set()
for e in pe.keys() & ce.keys():
    a, b = pe[e], ce[e]
    items.append({"id": "e" + e, "m": a["marca"] or b["marca"], "x": "e", "p": lado(a), "c": lado(b)})
    usados_p.add(a["id"])
    usados_c.add(b["id"])
n_ean = len(items)


# 2) Coincidencia probable: misma marca, mismo tamaño (±2 %) y nombre muy parecido
GEN_TOK = {"marca", "generico", "aplica", "na", "no"}
# Si una palabra de esta lista está en un producto y no en el otro, NO son el mismo producto
VARIANTES = {"organica", "organico", "light", "lite", "zero", "cero", "integral", "deslactosada", "descremada",
             "semidescremada", "diet", "vegano", "vegana", "baby", "mini", "jumbo", "extra", "premium",
             "picante", "dulce", "chocolate", "fresa", "vainilla", "natural", "original", "jalapeno",
             "habanero", "suavizante", "trocitos", "bbq", "barbacoa"}


def marca_compatible(a, b):
    return bool(a) and bool(b) and not (a <= GEN_TOK or b <= GEN_TOK) and (a <= b or b <= a)


def etapas(nombre):
    """'3+' / '1+' (etapas de leche, fórmulas): deben ser iguales en ambos."""
    return frozenset(re.findall(r"\b\d\+", norm(nombre)))


def cubo(q):
    return int(math.log(q) / 0.02)


indice = {}
for r in C:
    if r["id"] not in usados_c and r["ul"] and r["qty"] and r["qty"] > 0 and r["core"]:
        indice.setdefault((r["ul"], cubo(r["qty"])), []).append(r)

cands = []
for a in P:
    if a["id"] in usados_p or not (a["ul"] and a["qty"] and a["qty"] > 0 and a["core"] and a["bt"]):
        continue
    k = cubo(a["qty"])
    for kk in (k - 1, k, k + 1):
        for b in indice.get((a["ul"], kk), []):
            if abs(a["qty"] - b["qty"]) > 0.02 * max(a["qty"], b["qty"]):
                continue
            if not marca_compatible(a["bt"], b["bt"]):
                continue
            dif = a["core"] ^ b["core"]
            if dif & VARIANTES or etapas(a["nombre"]) != etapas(b["nombre"]):
                continue
            inter = len(a["core"] & b["core"])
            jac = inter / len(a["core"] | b["core"])
            chico = a["core"] if len(a["core"]) <= len(b["core"]) else b["core"]
            if jac >= 0.6 or (chico <= (a["core"] & b["core"]) and len(chico) >= 2 and len(dif) <= 1):
                cands.append((jac, a, b))
cands.sort(key=lambda x: -x[0])
for jac, a, b in cands:
    if a["id"] in usados_p or b["id"] in usados_c:
        continue
    usados_p.add(a["id"])
    usados_c.add(b["id"])
    items.append({"id": a["id"], "m": a["marca"] or b["marca"], "x": "f", "p": lado(a), "c": lado(b)})
n_fuzzy = len(items) - n_ean

# 3) Productos que solo están en una tienda
for r in P:
    if r["id"] not in usados_p:
        items.append({"id": r["id"], "m": r["marca"], "x": "", "p": lado(r), "c": None})
for r in C:
    if r["id"] not in usados_c:
        items.append({"id": r["id"], "m": r["marca"], "x": "", "p": None, "c": lado(r)})

print(f"Productos: {len(items)} · mismos por código de barras: {n_ean} · coincidencias probables: {n_fuzzy}")

# ───────────────────────── Página ─────────────────────────
SW = """// Guarda la página para que abra sin señal; se actualiza sola cuando hay internet.
const C = "precios-hn-v2";
self.addEventListener("install", e => { self.skipWaiting(); });
self.addEventListener("activate", e => e.waitUntil(
  caches.keys().then(ks => Promise.all(ks.filter(k => k !== C).map(k => caches.delete(k)))).then(() => self.clients.claim())));
self.addEventListener("fetch", e => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET" || u.origin !== location.origin) return;
  e.respondWith(caches.open(C).then(async c => {
    const hit = await c.match(e.request);
    const red = fetch(e.request).then(r => { if (r.ok) c.put(e.request, r.clone()); return r; }).catch(() => hit);
    return hit || red;
  }));
});
"""
MANIFEST = {"name": "Precios HN: Paiz vs La Colonia", "short_name": "Precios HN",
            "start_url": "./", "display": "standalone",
            "background_color": "#0f1317", "theme_color": "#0f1317"}


def js(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


html = (PLANTILLA.read_text(encoding="utf-8")
        .replace("__LISTA__", js(lista)).replace("__DATA__", js(items)).replace("__PFX__", js(PFX))
        .replace("__FP__", fecha_p).replace("__FC__", fecha_c))
SALIDA.mkdir(exist_ok=True)
(SALIDA / "index.html").write_text(html, encoding="utf-8")
(SALIDA / "sw.js").write_text(SW, encoding="utf-8")
(SALIDA / "manifest.webmanifest").write_text(json.dumps(MANIFEST, ensure_ascii=False), encoding="utf-8")
(SALIDA / ".nojekyll").write_text("", encoding="utf-8")
print("Listo ->", SALIDA / "index.html", f"({len(html)//1024} KB)")
