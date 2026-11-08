"""Genera los íconos de la app (mismo logo de la página) dentro del proyecto Android de Capacitor.
Uso: python android/iconos.py <carpeta android/app/src/main/res>"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw

res = Path(sys.argv[1])
FONDO = (15, 19, 23, 255)


def logo(tam, fondo_redondeado):
    """Cuadro con degradado azul→naranja y tres barras blancas."""
    s = tam * 4
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    grad = Image.new("RGBA", (s, s))
    px = grad.load()
    for y in range(s):
        for x in range(s):
            t = (x + y) / (2 * s)
            px[x, y] = (int(42 + (224 - 42) * t), int(104 + (86 - 104) * t), int(230 + (13 - 230) * t), 255)
    mask = Image.new("L", (s, s), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([0, 0, s, s], radius=int(s * 0.22) if fondo_redondeado else 0, fill=255)
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)
    ancho = s * 0.085
    for cx, alto in ((0.30, 0.30), (0.50, 0.50), (0.70, 0.38)):
        x0, x1 = s * cx - ancho, s * cx + ancho
        d.rounded_rectangle([x0, s * (0.72 - alto), x1, s * 0.72], radius=int(ancho * 0.6), fill=(255, 255, 255, 255))
    return img.resize((tam, tam), Image.LANCZOS)


def primer_plano(tam):
    """Capa frontal del ícono adaptable: el logo en el 62% central, fondo transparente."""
    lienzo = Image.new("RGBA", (tam, tam), (0, 0, 0, 0))
    g = logo(int(tam * 0.62), True)
    lienzo.paste(g, ((tam - g.width) // 2, (tam - g.height) // 2), g)
    return lienzo


dens = {"mdpi": 1, "hdpi": 1.5, "xhdpi": 2, "xxhdpi": 3, "xxxhdpi": 4}
for nombre, k in dens.items():
    carpeta = res / f"mipmap-{nombre}"
    carpeta.mkdir(parents=True, exist_ok=True)
    t = int(48 * k)
    base = logo(t, True)
    base.save(carpeta / "ic_launcher.png")
    circ = Image.new("RGBA", (t, t), (0, 0, 0, 0))
    m = Image.new("L", (t * 4, t * 4), 0)
    ImageDraw.Draw(m).ellipse([0, 0, t * 4, t * 4], fill=255)
    circ.paste(logo(t, False), (0, 0), m.resize((t, t), Image.LANCZOS))
    circ.save(carpeta / "ic_launcher_round.png")
    primer_plano(int(108 * k)).save(carpeta / "ic_launcher_foreground.png")

# fondo del ícono adaptable
for ruta in res.glob("values/ic_launcher_background.xml"):
    ruta.write_text('<?xml version="1.0" encoding="utf-8"?>\n<resources>\n    <color name="ic_launcher_background">#0F1317</color>\n</resources>\n')
# ícono adaptable (Android 8+): fondo de color + logo como capa frontal
ad = res / "mipmap-anydpi-v26"
ad.mkdir(parents=True, exist_ok=True)
xml = ('<?xml version="1.0" encoding="utf-8"?>\n'
       '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
       '    <background android:drawable="@color/ic_launcher_background"/>\n'
       '    <foreground android:drawable="@mipmap/ic_launcher_foreground"/>\n'
       '</adaptive-icon>\n')
(ad / "ic_launcher.xml").write_text(xml)
(ad / "ic_launcher_round.xml").write_text(xml)
vals = res / "values"
vals.mkdir(parents=True, exist_ok=True)
(vals / "ic_launcher_background.xml").write_text(
    '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n    <color name="ic_launcher_background">#0F1317</color>\n</resources>\n')
for viejo in (res / "drawable-v24" / "ic_launcher_foreground.xml", res / "drawable" / "ic_launcher_background.xml"):
    if viejo.exists():
        viejo.unlink()
print("Íconos listos")
