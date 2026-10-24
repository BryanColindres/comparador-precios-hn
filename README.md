# Comparador de precios: Paiz vs La Colonia (Honduras)

Página para el celular que compara precios de **Paiz** y **La Colonia**. Tiene tres pestañas:

- **Lista:** unos 44 productos básicos con el precio por libra, litro o unidad en cada tienda.
- **Calculadora:** escribes lo que te cobran en el mercado ("L. 20 por 3 libras") y te dice si es más barato o más caro que en cada supermercado.
- **Buscar:** todo el catálogo por nombre, con el precio por unidad.

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
docs/            lo que publica GitHub Pages (index.html, sw.js, manifest)
```

## Publicar con GitHub Pages

Repositorio → **Settings → Pages → Build and deploy → Deploy from a branch** → rama `main`, carpeta `/docs`.

## Notas

- La lista de productos básicos y sus palabras clave están al inicio de `generar_comparador.py` (`LISTA`, `CATS`, `EXTRA_EXC`). Si algo sale mal elegido, ajústalo ahí.
- Muchas frutas y verduras se venden **por unidad** en las tiendas, no por libra; en la página salen marcadas como `/unidad`.
- Los productos se cruzan entre tiendas por código de barras (EAN). Los que no lo tienen no se pueden comparar directo.
- Uso personal. Los scrapers esperan 0.8 s entre llamadas para no cargar los servidores de las tiendas.
