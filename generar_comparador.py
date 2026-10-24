"""Genera comparador.html (para el celular) desde los CSV de Paiz y La Colonia.
Uso:  pip install pandas
      python generar_comparador.py paiz_precios_FECHA.csv lacolonia_precios_FECHA.csv
Salida: comparador.html  -> pásalo al celular; funciona sin internet (salvo las fotos).

Pestañas: Lista (precio por libra/litro/unidad de lo básico) · Calculadora (precio del
mercado vs supermercados) · Buscar (todo el catálogo, con precio por unidad).
La LISTA de abajo es editable: cambia nombres o palabras clave a tu gusto.
"""
import re, sys, json, unicodedata, warnings
import pandas as pd

warnings.filterwarnings("ignore", message="This pattern is interpreted")

# (grupo, etiqueta, regex que debe aparecer, regex que NO debe aparecer, unidad: lb | L | u)
# Las regex se aplican al nombre del producto sin tildes y en minúsculas.
NO_PROC = r"salsa|pasta de|jugo|ketchup|kechup|enlatad|pure|sopa|encurtid|snack|chips|papitas|frita|congelad|mermelada|dulce de|deshidratad|polvo|saborizad|sabor a|galleta|cereal|yogurt|helado|vinagre|aderezo|mayonesa|condimento"
LISTA = [
    ("Verduras", "Tomate", r"\btomate", NO_PROC + r"|secos", "lb"),
    ("Verduras", "Cebolla", r"\bcebolla", NO_PROC + r"|polvo|morada", "lb"),
    ("Verduras", "Papa", r"\bpapa\b|\bpapas\b", NO_PROC, "lb"),
    ("Verduras", "Chile dulce", r"chile (dulce|pimiento)|pimiento", NO_PROC, "lb"),
    ("Verduras", "Zanahoria", r"zanahoria", NO_PROC, "lb"),
    ("Verduras", "Repollo", r"repollo", NO_PROC, "lb"),
    ("Verduras", "Pepino", r"pepino", NO_PROC, "lb"),
    ("Verduras", "Lechuga", r"lechuga", NO_PROC, "lb"),
    ("Verduras", "Ajo", r"\bajo\b|\bajos\b", NO_PROC + r"|molido|salsa", "lb"),
    ("Verduras", "Güisquil", r"guisquil|chayote", NO_PROC, "lb"),
    ("Verduras", "Yuca", r"\byuca", NO_PROC, "lb"),
    ("Verduras", "Aguacate", r"aguacate", NO_PROC + r"|aceite", "lb"),
    ("Frutas", "Plátano", r"platano", NO_PROC + r"|tostone|maduro frito", "lb"),
    ("Frutas", "Banano", r"banano|guineo", NO_PROC, "lb"),
    ("Frutas", "Naranja", r"\bnaranja", NO_PROC, "lb"),
    ("Frutas", "Limón", r"\blimon", NO_PROC, "lb"),
    ("Frutas", "Manzana", r"\bmanzana", NO_PROC, "lb"),
    ("Frutas", "Sandía", r"sandia", NO_PROC, "lb"),
    ("Frutas", "Piña", r"\bpina\b", NO_PROC, "lb"),
    ("Frutas", "Mango", r"\bmango", NO_PROC, "lb"),
    ("Frutas", "Papaya", r"papaya", NO_PROC, "lb"),
    ("Carnes", "Pechuga de pollo", r"pechuga", NO_PROC + r"|empanizad|nugget", "lb"),
    ("Carnes", "Muslo de pollo", r"muslo|encuentro", NO_PROC + r"|empanizad", "lb"),
    ("Carnes", "Pollo entero", r"pollo entero|pollo fresco", NO_PROC, "lb"),
    ("Carnes", "Carne molida de res", r"molida|molido", NO_PROC + r"|cerdo|pollo|pavo", "lb"),
    ("Carnes", "Carne para asar (res)", r"\basar\b", NO_PROC + r"|cerdo|pollo", "lb"),
    ("Carnes", "Costilla de cerdo", r"costilla", NO_PROC + r"|res\b", "lb"),
    ("Carnes", "Chuleta de cerdo", r"chuleta", NO_PROC, "lb"),
    ("Carnes", "Chorizo", r"chorizo", NO_PROC, "lb"),
    ("Carnes", "Tocino", r"tocino", NO_PROC, "lb"),
    ("Carnes", "Tilapia / pescado", r"tilapia|pescado", NO_PROC + r"|enlatad|atun|sardina", "lb"),
    ("Granos y despensa", "Frijol rojo", r"frijol", NO_PROC + r"|molido|refrito|enlatad|negro|blanco", "lb"),
    ("Granos y despensa", "Arroz", r"\barroz\b", NO_PROC + r"|con leche|pollo", "lb"),
    ("Granos y despensa", "Azúcar", r"azucar", NO_PROC + r"|sin azucar|splenda|stevia", "lb"),
    ("Granos y despensa", "Sal", r"\bsal\b", NO_PROC + r"|aderezo|con ajo", "lb"),
    ("Granos y despensa", "Harina de maíz", r"harina.*maiz|maiz.*harina|masa de maiz|maseca", NO_PROC, "lb"),
    ("Granos y despensa", "Pasta / espagueti", r"espagueti|spaghetti|fideo|macarron", NO_PROC + r"|salsa", "lb"),
    ("Granos y despensa", "Café molido", r"cafe", NO_PROC + r"|capuchino|instantaneo|soluble|3 en 1", "lb"),
    ("Granos y despensa", "Aceite vegetal", r"aceite", NO_PROC + r"|oliva|aguacate|coco|spray|motor", "L"),
    ("Lácteos y huevos", "Huevo", r"\bhuevo", NO_PROC + r"|codorniz|liquido|pascua", "u"),
    ("Lácteos y huevos", "Leche líquida", r"\bleche\b", NO_PROC + r"|polvo|condensada|evaporada|coco|chocolate|fresa|soya|almendra|avena", "L"),
    ("Lácteos y huevos", "Queso", r"\bqueso", NO_PROC + r"|rallado|crema|untable", "lb"),
    ("Lácteos y huevos", "Mantequilla", r"mantequilla", NO_PROC + r"|mani|cacahuate", "lb"),
    ("Panadería", "Tortillas", r"tortilla", NO_PROC + r"|chips|tostada|totopo|nacho", "u"),
]

# Categoría de la tienda donde debe estar el producto (regex sobre la ruta de categoría
# sin tildes, en minúsculas) y exclusiones extra por producto. Sin entrada = sin filtro.
VERD = r"frutas y verduras"
CATS = {
    "Tomate": VERD, "Cebolla": VERD, "Papa": VERD, "Chile dulce": VERD, "Zanahoria": VERD,
    "Repollo": VERD, "Pepino": VERD, "Lechuga": VERD, "Ajo": VERD, "Güisquil": VERD,
    "Yuca": VERD, "Aguacate": VERD, "Plátano": VERD, "Banano": VERD, "Naranja": VERD,
    "Limón": VERD, "Manzana": VERD, "Sandía": VERD, "Piña": VERD, "Mango": VERD, "Papaya": VERD,
    "Pechuga de pollo": r"carnes|pollo", "Muslo de pollo": r"carnes|pollo",
    "Pollo entero": r"carnes|pollo", "Carne molida de res": r"carnes|\bres\b",
    "Carne para asar (res)": r"carnes|\bres\b", "Costilla de cerdo": r"carnes|cerdo",
    "Chuleta de cerdo": r"carnes|cerdo", "Chorizo": r"embutidos", "Tocino": r"embutidos|tocino",
    "Tilapia / pescado": r"pescados|mariscos",
    "Frijol rojo": r"arroz, frijol|frijoles", "Arroz": r"arroz", "Azúcar": r"azucar|endulzante",
    "Sal": r"sal y condimentos|sopas, cremas y condimentos|especias",
    "Harina de maíz": r"harina", "Pasta / espagueti": r"pastas", "Café molido": r"cafe",
    "Aceite vegetal": r"aceites", "Huevo": r"huevo",
    "Leche líquida": r"leche entera|leche semi|deslactosada|leches liquidas",
    "Queso": r"queso", "Mantequilla": r"mantequilla", "Tortillas": r"tortill",
}
EXTRA_EXC = {
    "Pechuga de pollo": r"pavo|jamon", "Limón": r"albahaca|hierba|menta|te ",
    "Sal": r"pimienta|ajo|cebolla|adobo|aderezo|condimento",
    "Tilapia / pescado": r"cabeza|enlatad|gato|perro",
    "Pollo entero": r"menudo|fajita|pechuga|muslo|pierna|alas|molid|marinad|pavo|encuentro|filete|nugget|empaniz|caldo|hueso",
    "Plátano": r"precocid|tajada", "Café molido": r"crema|listo|te |betun|soluble",
    "Pasta / espagueti": r"salsa|instantane", "Mantequilla": r"mani|avellana|margarina",
    "Leche líquida": r"saborizada|malteada|bebida de",
    "Aceite vegetal": r"spray|oliva|manteca", "Tortillas de maíz": r"trigo|harina",
    "Huevo": r"chocolate|pascua", "Chorizo": r"pack|kimby",
    "Frijol rojo": r"molido|refrito|enlatad|instantane|negro",
}

from pathlib import Path

RAIZ = Path(__file__).resolve().parent
# Sin argumentos usa data/paiz_precios.csv y data/lacolonia_precios.csv y escribe docs/index.html
CSV_PAIZ = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "data" / "paiz_precios.csv"
CSV_COL = Path(sys.argv[2]) if len(sys.argv) > 2 else RAIZ / "data" / "lacolonia_precios.csv"
SALIDA = RAIZ / "docs"
for f in (CSV_PAIZ, CSV_COL):
    if not f.exists():
        sys.exit(f"No encuentro {f}. Corre primero los scrapers (carpeta scrapers/).")


def norm(s):
    s = unicodedata.normalize("NFD", str(s).lower())
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn")


W = {"kg": 2.20462, "kgs": 2.20462, "g": 1 / 453.592, "gr": 1 / 453.592, "grs": 1 / 453.592,
     "lb": 1, "lbs": 1, "libra": 1, "libras": 1, "oz": 1 / 16}
V = {"ml": 1 / 1000, "l": 1, "lt": 1, "lts": 1, "litro": 1, "litros": 1}
U = ("u", "und", "unid", "unidad", "unidades", "un", "unds")
UNIT_RE = r"(kgs?|grs?|g|lbs?|libras?|oz|ml|lts?|litros?|l|unidades|unidad|unids?|unds?|und|un|u)"


def unidad(nombre, precio):
    """Devuelve (precio por unidad, 'lb'|'L'|'u') o (None, None) si no se puede leer."""
    n = norm(nombre)
    if re.search(r"por libra|por lb|x lb\b|/lb\b", n):
        return precio, "lb"
    # "…Libra - 2 a 4 Unidades aprox." = precio por libra (salvo que indique "2 Lb" de peso)
    if re.search(r"\blibra\b", n) and not re.search(r"\d\s*(lbs?|libras?)\b", n):
        return precio, "lb"
    m = re.search(r"(\d+)\s*(?:x|pack de|pk)\s*(\d+(?:[.,]\d+)?)\s*" + UNIT_RE + r"\b", n)
    mult = 1
    fr = re.search(r"(\d+)\s*/\s*(\d+)\s*" + UNIT_RE + r"\b", n)  # "1/2 Lb"
    if fr and int(fr.group(2)) > 0:
        mult, cant, u = 1, int(fr.group(1)) / int(fr.group(2)), fr.group(3)
    elif m:
        mult, cant, u = int(m.group(1)), float(m.group(2).replace(",", ".")), m.group(3)
    else:
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*" + UNIT_RE + r"\b", n)
        if not m:
            # "X Unidad", "Venta Por Unidad", "... Un" al final = precio de 1 unidad
            if re.search(r"(\bx|\bpor)\s*unidad\b|\bunidad$|\bun$", n):
                return precio, "u"
            return None, None
        cant, u = float(m.group(1).replace(",", ".")), m.group(2)
    if cant <= 0:
        return None, None
    if u in W:
        tot, et = cant * mult * W[u], "lb"
    elif u in V:
        tot, et = cant * mult * V[u], "L"
    elif u in U:
        tot, et = cant * mult, "u"
    else:
        return None, None
    return (precio / tot, et) if tot > 0 else (None, None)


def cargar(ruta):
    df = pd.read_csv(ruta, dtype={"ean": str, "sku": str})
    # Paiz usa 13 dígitos (con 0 adelante) y La Colonia a veces 12: se igualan quitando
    # ceros a la izquierda. Códigos de menos de 8 dígitos (PLU internos) no se cruzan.
    df["ean"] = df["ean"].fillna("").str.strip().str.lstrip("0")
    df.loc[df["ean"].str.len() < 8, "ean"] = ""
    df = df[df["precio_actual"].fillna(0) > 0].copy()
    df = df.sort_values("precio_actual").drop_duplicates(["ean", "sku"])
    res = df.apply(lambda r: unidad(r["producto"], float(r["precio_actual"])), axis=1)
    df["up"] = [x[0] for x in res]
    df["ul"] = [x[1] for x in res]
    df["nn"] = df["producto"].map(norm)
    df["cn"] = df["categoria"].map(norm)
    return df


p, c = cargar(CSV_PAIZ), cargar(CSV_COL)
fecha_p = str(pd.read_csv(CSV_PAIZ, usecols=["fecha"])["fecha"].iloc[0])
fecha_c = str(pd.read_csv(CSV_COL, usecols=["fecha"])["fecha"].iloc[0])


def mejor(df, etiqueta, inc, exc, ul, minimo=0):
    exc = exc + (("|" + EXTRA_EXC[etiqueta]) if etiqueta in EXTRA_EXC else "")
    m = (df["ul"] == ul) & df["nn"].str.contains(inc, regex=True) \
        & ~df["nn"].str.contains(exc, regex=True)
    if etiqueta in CATS:
        m &= df["cn"].str.contains(CATS[etiqueta], regex=True)
    d = df[m]
    if d.empty:
        return None
    med = d["up"].median()
    d = d[(d["up"] >= 0.15 * med) & (d["up"] >= minimo)]  # descarta precios absurdamente bajos por errores de tamaño en el nombre
    if d.empty:
        return None
    r = d.sort_values("up").iloc[0]
    # [precio por unidad más bajo, producto, precio del empaque, precio típico (mediana), # productos, unidad]
    return [round(float(r["up"]), 2), r["producto"], round(float(r["precio_actual"]), 2),
            round(float(d["up"].median()), 2), int(len(d)), ul]


def buscar(df, g, n, i, e, u):
    prod = g in ("Verduras", "Frutas")
    r = mejor(df, n, i, e, u, minimo=3 if prod and u == "lb" else 0)  # fruta/verdura < L.3/lb = error de dato
    if r is None and prod and u == "lb":
        r = mejor(df, n, i, e, "u")  # muchas frutas/verduras se venden por unidad
    return r


lista = [{"g": g, "n": n, "u": u, "p": buscar(p, g, n, i, e, u), "c": buscar(c, g, n, i, e, u)}
         for g, n, i, e, u in LISTA]
print("Lista fija: encontró", sum(1 for x in lista if x["p"]), "en Paiz y",
      sum(1 for x in lista if x["c"]), "en La Colonia de", len(lista))
print("Sin resultado:", [x["n"] for x in lista if not x["p"] and not x["c"]])


def fila(r):
    pl = round(float(r["precio_lista"]), 2) if pd.notna(r.get("precio_lista")) else 0
    up = round(float(r["up"]), 2) if pd.notna(r["up"]) else 0
    return [round(float(r["precio_actual"]), 2), pl, up, r["ul"] if isinstance(r["ul"], str) else ""]


def img(r):
    return r.get("imagen_url") if isinstance(r.get("imagen_url"), str) else ""


pe = {r["ean"]: r for _, r in p.iterrows() if r["ean"]}
ce = {r["ean"]: r for _, r in c.iterrows() if r["ean"]}
items = []
for e in set(pe) | set(ce):
    a, b = pe.get(e), ce.get(e)
    base = a if a is not None else b
    items.append({"e": e, "n": base["producto"], "m": base.get("marca") or "",
                  "i": img(a) if a is not None and img(a) else (img(b) if b is not None else ""),
                  "p": fila(a) if a is not None else None, "c": fila(b) if b is not None else None})
for tienda, df in (("p", p), ("c", c)):
    for _, r in df[df["ean"] == ""].iterrows():
        items.append({"e": "", "n": r["producto"], "m": r.get("marca") or "", "i": img(r),
                      "p": fila(r) if tienda == "p" else None,
                      "c": fila(r) if tienda == "c" else None})

PLANTILLA = r"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Precios HN</title>
<link rel="manifest" href="manifest.webmanifest"><meta name="theme-color" content="#1b1f24">
<style>
:root{--bg:#f6f7f9;--cd:#fff;--tx:#1b1f24;--mu:#6b7280;--bd:#e3e6ea;--ok:#15803d;--ba:#b91c1c}
@media(prefers-color-scheme:dark){:root{--bg:#0f1317;--cd:#1a2027;--tx:#e8ecf0;--mu:#98a2b0;--bd:#2b333c;--ok:#4ade80;--ba:#f87171}}
*{box-sizing:border-box}body{margin:0;font:16px/1.35 system-ui,sans-serif;background:var(--bg);color:var(--tx)}
.tabs{position:sticky;top:0;z-index:5;display:flex;background:var(--cd);border-bottom:1px solid var(--bd)}
.tabs button{flex:1;padding:13px 4px;font:inherit;font-weight:600;border:0;background:none;color:var(--mu);border-bottom:3px solid transparent}
.tabs .on{color:var(--tx);border-color:var(--tx)}
.pane{display:none;padding-bottom:30px}.pane.on{display:block}
.mt{color:var(--mu);font-size:12px;padding:8px 12px}
h3{margin:14px 12px 4px;font-size:13px;text-transform:uppercase;letter-spacing:.04em;color:var(--mu)}
.hd,.rw{display:grid;grid-template-columns:1.1fr 1fr 1fr;gap:6px;padding:8px 12px;align-items:center}
.hd{font-size:11px;color:var(--mu);padding-top:2px}
.rw{background:var(--cd);border-top:1px solid var(--bd);font-size:15px}
.rw .nm{font-weight:600}.rw small{display:block;color:var(--mu);font-size:10.5px;font-weight:400;line-height:1.2;
 overflow:hidden;text-overflow:ellipsis;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.pc{font-weight:700}.w{color:var(--ok)}.l{color:var(--ba)}.ut{font-size:11px;color:var(--mu)}
.cal{padding:12px}.cal label{display:block;font-size:13px;color:var(--mu);margin:10px 0 4px}
select,input{width:100%;font:inherit;padding:13px;border:1px solid var(--bd);border-radius:10px;background:var(--cd);color:var(--tx)}
.two{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.res{margin-top:16px;background:var(--cd);border:1px solid var(--bd);border-radius:12px;padding:14px}
.res .big{font-size:20px;font-weight:700}.res .ln{display:flex;justify-content:space-between;padding:6px 0;border-top:1px solid var(--bd);margin-top:6px}
.cd{display:flex;gap:10px;background:var(--cd);border:1px solid var(--bd);border-radius:12px;margin:8px 10px;padding:10px}
.cd img{width:60px;height:60px;object-fit:contain;background:#fff;border-radius:8px;flex:none}
.cd .nm{font-weight:600;font-size:14px}.br{color:var(--mu);font-size:12px}
.pr{display:flex;gap:8px;margin-top:6px}.pr div{flex:1;border:1px solid var(--bd);border-radius:8px;padding:5px 8px;font-size:13px}
.pr small{display:block;color:var(--mu);font-size:11px}.pr .win{border-color:var(--ok);color:var(--ok)}
.pr s{color:var(--mu);font-size:11px}
</style></head><body>
<div class="tabs"><button data-t="t1" class="on">Lista</button><button data-t="t2">Calculadora</button><button data-t="t3">Buscar</button></div>
<div id="t1" class="pane on"><div class="mt" id="info"></div>
<div class="hd" style="padding-top:8px"><span></span><span>Paiz</span><span>La Colonia</span></div><div id="lista"></div></div>
<div id="t2" class="pane"><div class="cal">
<label>Producto</label><select id="cp"></select>
<div class="two"><div><label>Precio en el mercado (L.)</label><input id="cpr" type="number" inputmode="decimal" placeholder="20"></div>
<div><label>Cantidad</label><input id="cca" type="number" inputmode="decimal" placeholder="3" value="1"></div></div>
<label>Unidad</label><select id="cun"></select>
<div class="res" id="cres"><span class="mt">Escribe el precio y la cantidad.</span></div></div></div>
<div id="t3" class="pane"><div style="padding:10px"><input id="q" type="search" placeholder="Buscar producto o marca…" autocomplete="off"></div>
<div id="out"></div></div>
<script>
const LISTA=__LISTA__,D=__DATA__,FP="__FP__",FC="__FC__";
const $=i=>document.getElementById(i),L=n=>"L. "+n.toFixed(2),ET={lb:"lb",L:"litro",u:"unidad"};
const UN={lb:[["lb",1],["kg",2.20462],["g",1/453.592],["oz",1/16]],L:[["litro",1],["ml",.001]],u:[["unidad",1],["docena",12]]};
function norm(s){return s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g,"")}
// ---- Calculadora (función pura, para poder probarla)
function calcular(it,precio,cant,fac){
  if(!(precio>0&&cant>0))return null;
  const mer=precio/(cant*fac);
  const r={mer,unidad:ET[it.u],tiendas:[]};
  for(const[n,s]of[["Paiz",it.p],["La Colonia",it.c]]){
    if(!s){r.tiendas.push({n,sin:true});continue}
    if(s[5]!==it.u){r.tiendas.push({n,otra:ET[s[5]],up:s[0],prod:s[1]});continue}
    const d=mer-s[0];r.tiendas.push({n,up:s[0],prod:s[1],d,pct:d/s[0]*100});
  }return r}
// ---- Lista
$("info").textContent="Paiz al "+FP+" · La Colonia al "+FC+". Precio más bajo encontrado por categoría; revisa el nombre.";
let h="",g="";
LISTA.forEach((x,i)=>{
  if(x.g!=g){g=x.g;h+=`<h3>${g}</h3>`}
  const a=x.p,b=x.c,w=a&&b&&a[5]==b[5]?(a[0]<b[0]?"p":a[0]>b[0]?"c":""):"";
  const cel=(s,k)=>s?`<div><span class="pc ${w&&w==k?"w":w?"l":""}">${L(s[0])}</span> <span class="ut">/${ET[s[5]]}</span><small>${s[1]}</small><small>típico ${L(s[3])} · ${s[4]} prod.</small></div>`:`<div class="mt" style="padding:0">—</div>`;
  h+=`<div class="rw"><div class="nm">${x.n}<small>por ${ET[x.u]}</small></div>${cel(a,"p")}${cel(b,"c")}</div>`});
$("lista").innerHTML=h;
// ---- Calculadora UI
$("cp").innerHTML=LISTA.map((x,i)=>`<option value="${i}">${x.n}</option>`).join("");
function unidades(){const it=LISTA[+$("cp").value];$("cun").innerHTML=UN[it.u].map((u,i)=>`<option value="${i}">${u[0]}</option>`).join("");calc()}
function calc(){
  const it=LISTA[+$("cp").value],fac=UN[it.u][+$("cun").value][1];
  const r=calcular(it,parseFloat($("cpr").value),parseFloat($("cca").value),fac);
  if(!r){$("cres").innerHTML='<span class="mt">Escribe el precio y la cantidad.</span>';return}
  let o=`<div class="big">${L(r.mer)} por ${r.unidad}</div>`;
  r.tiendas.forEach(t=>{
    if(t.otra){o+=`<div class="ln"><span>${t.n}<br><small class="mt" style="padding:0">${t.prod.slice(0,40)}</small></span><span class="mt" style="padding:0">solo ${L(t.up)} por ${t.otra}</span></div>`;return}
    if(t.sin){o+=`<div class="ln"><span>${t.n}</span><span class="mt" style="padding:0">sin dato</span></div>`;return}
    const barato=t.d<0,igual=Math.abs(t.d)<.005;
    o+=`<div class="ln"><span>${t.n}<br><small class="mt" style="padding:0">${L(t.up)} · ${t.prod.slice(0,40)}</small></span>
    <span class="${igual?"":barato?"w":"l"}"><b>${igual?"igual":(barato?"mercado −":"mercado +")+L(Math.abs(t.d))}</b></span></div>`});
  $("cres").innerHTML=o}
$("cp").onchange=unidades;["cpr","cca","cun"].forEach(i=>$(i).oninput=calc);unidades();
// ---- Buscar
D.forEach(x=>x.k=norm(x.n+" "+x.m)+" "+x.e);
function box(t,s,w){if(!s)return`<div><small>${t}</small>—</div>`;
  const u=s[2]?`<small>${L(s[2])} / ${ET[s[3]]}</small>`:"";
  return`<div class="${w?"win":""}"><small>${t}</small><b>${L(s[0])}</b>${s[1]>s[0]?` <s>${L(s[1])}</s>`:""}${u}</div>`}
function card(x){const d=x.p&&x.c?x.p[0]-x.c[0]:null;
  return`<div class="cd"><img loading="lazy" referrerpolicy="no-referrer" src="${x.i}" onerror="this.style.visibility='hidden'">
  <div style="flex:1"><div class="nm">${x.n}</div><div class="br">${x.m}</div>
  <div class="pr">${box("Paiz",x.p,d!=null&&d<0)}${box("La Colonia",x.c,d!=null&&d>0)}</div></div></div>`}
function go(){const ws=norm($("q").value.trim()).split(/\s+/).filter(Boolean);
  if(!ws.length){$("out").innerHTML='<div class="mt">Escribe para buscar en todo el catálogo ('+D.length+' productos).</div>';return}
  const r=D.filter(x=>ws.every(w=>x.k.includes(w))).sort((a,b)=>(!!(b.p&&b.c))-(!!(a.p&&a.c))||a.n.localeCompare(b.n));
  $("out").innerHTML=r.slice(0,50).map(card).join("")||'<div class="mt">Sin resultados.</div>'}
$("q").oninput=go;go();
// ---- Pestañas
document.querySelectorAll(".tabs button").forEach(b=>b.onclick=()=>{
  document.querySelectorAll(".tabs button,.pane").forEach(x=>x.classList.remove("on"));
  b.classList.add("on");$(b.dataset.t).classList.add("on")});
if("serviceWorker" in navigator)navigator.serviceWorker.register("sw.js").catch(()=>{});
</script></body></html>"""

SW = """// Guarda la página para que abra sin señal; se actualiza sola cuando hay internet.
const C = "precios-hn-v1";
self.addEventListener("install", e => { self.skipWaiting(); });
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));
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
            "background_color": "#1b1f24", "theme_color": "#1b1f24"}

out = (PLANTILLA
       .replace("__LISTA__", json.dumps(lista, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
       .replace("__DATA__", json.dumps(items, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
       .replace("__FP__", fecha_p).replace("__FC__", fecha_c))
SALIDA.mkdir(exist_ok=True)
(SALIDA / "index.html").write_text(out, encoding="utf-8")
(SALIDA / "sw.js").write_text(SW, encoding="utf-8")
(SALIDA / "manifest.webmanifest").write_text(json.dumps(MANIFEST, ensure_ascii=False), encoding="utf-8")
(SALIDA / ".nojekyll").write_text("", encoding="utf-8")
print(len(items), "productos ->", SALIDA / "index.html", f"({len(out)//1024} KB)")
