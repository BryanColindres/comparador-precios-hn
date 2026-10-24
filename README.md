# Comparador de precios: Paiz vs La Colonia (Honduras)

Página para el celular que compara precios de **Paiz** y **La Colonia**, con cuatro pestañas:

- **Lista:** ~46 productos básicos (ordenados A–Z por grupo) con el precio por libra, litro o unidad en cada tienda, quién gana y cuánto se ahorra.
- **Calculadora:** productos en orden alfabético; escribes lo que te cobran en el mercado y eliges la unidad (lb, kg, g, oz, unidad, docena…). Compara solo en la misma medida: si una tienda lo vende únicamente por libra y tú por unidad, lo dice en vez de inventar una comparación.
- **Buscar:** todo el catálogo; da igual singular/plural (huevo/huevos) y acentos; filtro Todas / solo Paiz / solo La Colonia / En ambas; ordena por precio, precio por unidad o mayor ahorro; botón **Similares** para ver el equivalente en la otra tienda.
- **Escáner:** el botón de código de barras en Buscar abre la cámara y muestra el producto en cada tienda (o escribes el número). Necesita HTTPS (GitHub Pages lo es) y permiso de cámara; en iPhone carga un lector extra, así que pide internet.
- **Mercado:** tu lista de compra del mercado con cantidad, unidad y precio pagado; suma lo gastado, tiene presupuesto opcional y, si el producto está en la lista básica, te dice cuánto más o menos pagaste que en el súper. Se guarda en el celular y se puede compartir por WhatsApp.
- **Canasta:** suma el total por tienda (se guarda en el celular).

Incluye tema claro/oscuro.

Los precios son una **foto del día en que se corrieron los scrapers** (la fecha aparece arriba en la página).

## Para la familia

Abre el link de la página (ver "Publicar" abajo) en el celular. Para tenerla como app: en Chrome, menú ⋮ → *Agregar a la pantalla principal*; en iPhone (Safari), compartir → *Agregar a inicio*. Ábrela una vez con internet y después carga también sin señal. Las fotos sí necesitan internet.

## Actualizar los precios (a mano)

```bash
pip install -r requirements.txt

python scrapers/scrape_paiz.py          # genera data/paiz_precios.csv
python scrapers/scrape_lacolonia.py     # genera data/lacolonia_precios.csv
python generar_comparador.py            # genera docs/index.html

git add data docs
git commit -m "Precios actualizados"
git push
```

En 1–2 minutos GitHub Pages publica la versión nueva.

`scrape_lacolonia.py --lista` solo muestra los departamentos; con nombres (`Abarrotes Lácteos`) baja solo esos.

## Estructura

```
scrapers/        scrape_paiz.py, scrape_lacolonia.py   (bajan precios de las APIs públicas de VTEX)
data/            CSV más recientes de cada tienda
generar_comparador.py   une los CSV y crea la página
plantilla.html   diseño de la página (se rellena con los datos)
docs/            lo que publica GitHub Pages (index.html, sw.js, manifest)
```

## Publicar con GitHub Pages

Repositorio → **Settings → Pages → Build and deploy → Deploy from a branch** → rama `main`, carpeta `/docs`.

## Notas

- La lista de productos básicos y sus palabras clave están al inicio de `generar_comparador.py` (`LISTA`, `CATS`, `EXTRA_EXC`). Si algo sale mal elegido, ajústalo ahí.
- Muchas frutas y verduras se venden **por unidad** en las tiendas, no por libra; en la página salen marcadas como `/unidad`.
- Los productos se cruzan entre tiendas de dos formas: por código de barras (**Mismo producto**) y, si las marcas tienen códigos distintos, por coincidencia de marca + tamaño exacto (±2%) + nombre muy parecido (**Coincidencia probable**). Lo demás se compara con «Similares» (mismo tipo y tamaño parecido, ordenado por precio por unidad).
- Los huevos de 15/20/30 unidades se comparan por precio por unidad.
- Uso personal. Los scrapers esperan 0.8 s entre llamadas para no cargar los servidores de las tiendas.
