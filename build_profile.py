#!/usr/bin/env python3
"""
Genera dark_mode.svg y light_mode.svg para el README del perfil de GitHub.

Uso normal (lo ejecuta tambien la GitHub Action):
    python build_profile.py

Regenerar el retrato ASCII a partir de una foto (solo en el computador local):
    pip install pillow numpy rembg onnxruntime
    python build_profile.py --regen-ascii --foto ruta/a/foto.jpg

Vista previa sin animacion (para revisar el diseno en un visor de imagenes):
    python build_profile.py --estatico
"""
import argparse
import html
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
USUARIO = os.environ.get("GITHUB_USER", "santiagohb2830")
TOKEN = os.environ.get("GITHUB_TOKEN", "")

# ----------------------------------------------------------------------
# Contenido del panel derecho. Editar aqui.
# ----------------------------------------------------------------------
TITULO = "santiago@hernandez"

PERFIL = [
    ("kv", "SO", "Windows, Ubuntu Server, MacOS"),
    ("kv", "Host", "Pontificia Universidad Javeriana"),
    ("kv", "Kernel", "Ingeniería de Sistemas, 8vo semestre"),
    ("kv", "Enfoque", "Ciencia de Datos"),
    ("kv", "IDE", "VS Code, IntelliJ IDEA,"),
    ("kv", "Herramientas", "Git, Docker, Postman, Google Colab, ClaudeCode, ChatGPT, Excel, Power BI, ArcGIS"),
    ("blank",),
    ("kv", "Lenguajes.Programación", "Python, Java, C++, SQL"),
    ("kv", "Lenguajes.Datos", "DAX, Power BI, ArcGIS"),
    ("kv", "Lenguajes.naturales", "Español, Inglés"),
    ("blank",),
    ("kv", "Pasatiempos.Software", "Bots y automatización con IA"),
    ("kv", "Pasatiempos.Hardware", "Electrónica, mecánica de moto"),
    ("blank",),
    ("seccion", "Contacto"),
    ("kv", "Correo", "santiagohb2830@gmail.com"),
    ("kv", "LinkedIn", "santiagohb2830"),
    ("blank",),
    ("seccion", "GitHub"),
    ("stat", "Repos", "repos"),
    ("stat", "Contribuido en", "contribuidos"),
    ("stat", "Commits", "commits"),
    ("stat", "Estrellas", "estrellas"),
    ("stat", "Seguidores", "seguidores"),
]

# ----------------------------------------------------------------------
# Medidas y tiempos
# ----------------------------------------------------------------------
COLS = 56            # columnas del retrato ASCII
CW = 8.4             # ancho de caracter (px)
LH = 15.6            # alto de linea del retrato (px)
FS = 14              # tamano de fuente (px)
MARGEN = 22
ANCHO_INFO = 56      # caracteres por linea del panel derecho
LH_INFO = 19.8
PASO_ASCII = 0.07    # segundos entre filas del barrido
T0_INFO = 0.35       # inicio del tecleo del panel derecho
PASO_INFO = 0.13     # segundos entre lineas del panel derecho
DUR_LINEA = 0.55     # duracion del tecleo de cada linea

FUENTE = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'DejaVu Sans Mono',monospace"

TEMAS = {
    "dark": {
        "fondo": "#0d1117", "borde": "#30363d", "ascii": "#c9d1d9",
        "clave": "#ffa657", "valor": "#79c0ff", "tenue": "#484f58",
        "titulo": "#e6edf3", "acento": "#00bcd4",
    },
    "light": {
        "fondo": "#f6f8fa", "borde": "#d0d7de", "ascii": "#24292f",
        "clave": "#953800", "valor": "#0a3069", "tenue": "#afb8c1",
        "titulo": "#1f2328", "acento": "#00838f",
    },
}

# ----------------------------------------------------------------------
# Retrato ASCII (solo se usa con --regen-ascii)
# ----------------------------------------------------------------------
RAMPA = " .:-=+*#%@"
# Recorte (izq, arriba, der, abajo) de la foto original. Ajustar si se cambia la foto.
RECORTE = (275, 255, 855, 905)


def generar_ascii(ruta_foto):
    import numpy as np
    from PIL import Image, ImageFilter
    from rembg import new_session, remove

    foto = Image.open(ruta_foto).convert("RGB")
    sesion = new_session("u2net_human_seg")
    mascara = remove(foto, session=sesion, only_mask=True)

    gris = foto.convert("L").crop(RECORTE).filter(ImageFilter.GaussianBlur(1.5))
    masc = mascara.convert("L").crop(RECORTE).filter(ImageFilter.GaussianBlur(2))
    w, h = gris.size
    filas = int(COLS * (h / w) * (CW / LH))

    a = np.asarray(gris.resize((COLS, filas), Image.BOX), dtype=float) / 255.0
    m = np.asarray(masc.resize((COLS, filas), Image.BOX), dtype=float) / 255.0

    dentro = m > 0.5
    lo, hi = np.percentile(a[dentro], 3), np.percentile(a[dentro], 97)
    a = np.clip((a - lo) / (hi - lo), 0, 1) ** 0.9

    for modo in ("dark", "light"):
        dens = 1 - a  # zonas oscuras de la foto = caracteres densos (mas legible)
        dens = 0.08 + 0.92 * dens
        idx = np.clip((dens * (len(RAMPA) - 1)).round().astype(int), 1, len(RAMPA) - 1)
        idx = np.where(m > 0.45, idx, 0)
        lineas = ["".join(RAMPA[i] for i in fila).rstrip() for fila in idx]
        (RAIZ / f"ascii_{modo}.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print(f"Retrato ASCII generado: {filas} filas x {COLS} columnas")


# ----------------------------------------------------------------------
# Estadísticas de GitHub
# ----------------------------------------------------------------------
def _get(url):
    cab = {"Accept": "application/vnd.github+json", "User-Agent": "perfil-readme"}
    if TOKEN:
        cab["Authorization"] = f"Bearer {TOKEN}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=cab), timeout=20) as r:
        return json.load(r)


def _graphql(consulta):
    cuerpo = json.dumps({"query": consulta}).encode()
    cab = {
        "Authorization": f"Bearer {TOKEN}",
        "User-Agent": "perfil-readme",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request("https://api.github.com/graphql", data=cuerpo, headers=cab)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def obtener_estadisticas():
    est = {
        "repos": "-",
        "contribuidos": "-",
        "commits": "-",
        "estrellas": "-",
        "seguidores": "-",
    }
    if USUARIO == "TU_USUARIO":
        return est
    try:
        u = _get(f"https://api.github.com/users/{USUARIO}")
        est["repos"] = f"{u['public_repos']:,}"
        est["seguidores"] = f"{u['followers']:,}"
        estrellas, pagina = 0, 1
        while True:
            lote = _get(f"https://api.github.com/users/{USUARIO}/repos?per_page=100&page={pagina}")
            estrellas += sum(r["stargazers_count"] for r in lote)
            if len(lote) < 100:
                break
            pagina += 1
        est["estrellas"] = f"{estrellas:,}"
        c = _get(f"https://api.github.com/search/commits?q=author:{USUARIO}&per_page=1")
        est["commits"] = f"{c['total_count']:,}"
    except (OSError, KeyError, ValueError) as e:
        print(f"Aviso: no se pudieron obtener todas las estadisticas ({e})", file=sys.stderr)

    # Repos ajenos a los que ha contribuido (GraphQL exige token)
    if TOKEN:
        try:
            g = _graphql(
                'query { user(login: "%s") { repositoriesContributedTo(first: 1, '
                "includeUserRepositories: false, contributionTypes: "
                "[COMMIT, PULL_REQUEST, ISSUE, PULL_REQUEST_REVIEW]) { totalCount } } }" % USUARIO
            )
            total = g["data"]["user"]["repositoriesContributedTo"]["totalCount"]
            est["contribuidos"] = f"{total:,}"
        except (OSError, KeyError, TypeError, ValueError) as e:
            print(f"Aviso: no se pudo obtener 'contribuido en' ({e})", file=sys.stderr)
    else:
        print("Aviso: sin GITHUB_TOKEN no se puede consultar 'contribuido en'", file=sys.stderr)
    return est


# ----------------------------------------------------------------------
# Construccion del SVG
# ----------------------------------------------------------------------
def construir_svg(lineas_ascii, tema, est, animado=True):
    c = TEMAS[tema]
    filas = len(lineas_ascii)
    alto_ascii = filas * LH
    x_info = MARGEN + COLS * CW + 26
    ancho = int(round(x_info + ANCHO_INFO * CW + MARGEN))
    alto = int(round(alto_ascii + 2 * MARGEN))
    n_info = len(PERFIL) + 1  # +1 por la linea de titulo
    y_info0 = MARGEN + (alto_ascii - n_info * LH_INFO) / 2 + FS
    dur_barrido = filas * PASO_ASCII

    p = []
    p.append('<?xml version="1.0" encoding="UTF-8"?>')
    p.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{ancho}" height="{alto}" '
        f'viewBox="0 0 {ancho} {alto}" role="img" aria-label="Perfil de Santiago Hernández">'
    )
    p.append("<style>")
    p.append(
        f"text{{font-family:{FUENTE};font-size:{FS}px;white-space:pre}}"
        f".a{{fill:{c['ascii']}}}.k{{fill:{c['clave']}}}.v{{fill:{c['valor']}}}"
        f".d{{fill:{c['tenue']}}}.h{{fill:{c['titulo']};font-weight:600}}"
    )
    p.append("</style>")
    p.append("<defs>")
    p.append(
        f'<linearGradient id="estela" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{c["acento"]}" stop-opacity="0"/>'
        f'<stop offset="1" stop-color="{c["acento"]}" stop-opacity="0.22"/></linearGradient>'
    )

    # Clips de tecleo del panel derecho
    tiempos = {}
    orden = 0
    for i, item in enumerate(PERFIL, start=1):
        if item[0] == "blank":
            continue
        tiempos[i] = T0_INFO + (orden + 1) * PASO_INFO
        orden += 1
    t_titulo = T0_INFO
    t_fin = max(tiempos.values()) + DUR_LINEA

    def clip(id_, y, inicio):
        if not animado:
            return ""
        valores = ";".join(f"{k * CW:.1f}" for k in range(ANCHO_INFO + 5))
        return (
            f'<clipPath id="{id_}"><rect x="{x_info:.1f}" y="{y - FS:.1f}" width="0" height="{FS + 6}">'
            f'<animate attributeName="width" values="{valores}" calcMode="discrete" '
            f'begin="{inicio:.2f}s" dur="{DUR_LINEA}s" fill="freeze"/></rect></clipPath>'
        )

    p.append(clip("t0", y_info0, t_titulo))
    for i, t in tiempos.items():
        p.append(clip(f"t{i}", y_info0 + i * LH_INFO, t))
    p.append("</defs>")

    # Fondo
    p.append(
        f'<rect x="0.5" y="0.5" width="{ancho - 1}" height="{alto - 1}" rx="14" '
        f'fill="{c["fondo"]}" stroke="{c["borde"]}"/>'
    )

    # Retrato ASCII: aparece fila por fila, de arriba hacia abajo
    for i, linea in enumerate(lineas_ascii):
        if not linea.strip():
            continue
        y = MARGEN + FS + i * LH
        largo = len(linea) * CW
        ini = ' opacity="0"' if animado else ""
        p.append(
            f'<text class="a" x="{MARGEN}" y="{y:.1f}" textLength="{largo:.1f}" '
            f'lengthAdjust="spacing" xml:space="preserve"{ini}>{html.escape(linea, quote=False)}'
            + (f'<set attributeName="opacity" to="1" begin="{i * PASO_ASCII + 0.05:.2f}s" fill="freeze"/>' if animado else "")
            + "</text>"
        )

    # Linea de barrido
    if animado:
        y_a, y_b = MARGEN, MARGEN + alto_ascii
        p.append(
            f'<g opacity="0"><set attributeName="opacity" to="1" begin="0s" fill="freeze"/>'
            f'<rect x="{MARGEN}" y="{y_a - 14}" width="{COLS * CW:.1f}" height="14" fill="url(#estela)">'
            f'<animate attributeName="y" from="{y_a - 14}" to="{y_b - 14}" dur="{dur_barrido:.2f}s" begin="0s" fill="freeze"/></rect>'
            f'<rect x="{MARGEN}" y="{y_a}" width="{COLS * CW:.1f}" height="1.5" fill="{c["acento"]}">'
            f'<animate attributeName="y" from="{y_a}" to="{y_b}" dur="{dur_barrido:.2f}s" begin="0s" fill="freeze"/></rect>'
            f'<animate attributeName="opacity" values="1;1;0" keyTimes="0;0.97;1" '
            f'dur="{dur_barrido + 0.1:.2f}s" begin="0s" fill="freeze"/></g>'
        )

    # Panel derecho. Cada fila coloca sus partes en posiciones absolutas:
    # la clave a la izquierda, el valor pegado al borde derecho y la linea de
    # puntos dibujada como figura. Asi no depende del ancho exacto de la fuente
    # que tenga cada navegador.
    x_der = x_info + ANCHO_INFO * CW   # borde derecho del panel
    HOLGURA = 1.06                     # margen por si la fuente resulta mas ancha

    def esc(t):
        return html.escape(t, quote=False)

    def fila(id_clip, y, item):
        tipo = item[0]
        cp = f' clip-path="url(#{id_clip})"' if animado else ""
        guion = f'stroke="{c["tenue"]}"'
        if tipo in ("titulo", "seccion"):
            prefijo = "- " if tipo == "seccion" else ""
            nombre = item[1]
            texto = (
                f'<text y="{y:.1f}" xml:space="preserve">'
                + (f'<tspan x="{x_info:.1f}" class="d">{prefijo}</tspan><tspan class="h">{esc(nombre)}</tspan>'
                   if prefijo else f'<tspan x="{x_info:.1f}" class="h">{esc(nombre)}</tspan>')
                + "</text>"
            )
            x1 = x_info + (len(prefijo) + len(nombre)) * CW * HOLGURA + 8
            linea = (
                f'<line x1="{x1:.1f}" x2="{x_der:.1f}" y1="{y - 4:.1f}" y2="{y - 4:.1f}" '
                f'{guion} stroke-width="1"/>'
            )
            return f"<g{cp}>{texto}{linea}</g>"

        clave = item[1]
        valor = est[item[2]] if tipo == "stat" else item[2]
        texto = (
            f'<text y="{y:.1f}" xml:space="preserve">'
            f'<tspan x="{x_info:.1f}" class="d">. </tspan>'
            f'<tspan class="k">{esc(clave)}:</tspan>'
            f'<tspan x="{x_der:.1f}" text-anchor="end" class="v">{esc(valor)}</tspan>'
            "</text>"
        )
        x1 = x_info + (2 + len(clave) + 1) * CW * HOLGURA + 8
        x2 = x_der - len(valor) * CW * HOLGURA - 8
        puntos = ""
        if x2 - x1 >= 10:
            puntos = (
                f'<line x1="{x1:.1f}" x2="{x2:.1f}" y1="{y - 2.5:.1f}" y2="{y - 2.5:.1f}" '
                f'{guion} stroke-width="1.5" stroke-linecap="round" '
                f'stroke-dasharray="0.01 {CW:.1f}"/>'
            )
        return f"<g{cp}>{texto}{puntos}</g>"

    p.append(fila("t0", y_info0, ("titulo", TITULO)))
    for i, item in enumerate(PERFIL, start=1):
        if item[0] != "blank":
            p.append(fila(f"t{i}", y_info0 + i * LH_INFO, item))

    # Cursor parpadeante al final
    y_ult = y_info0 + len(PERFIL) * LH_INFO
    x_cur = x_der + 4
    if animado:
        p.append(
            f'<rect x="{x_cur:.1f}" y="{y_ult - FS + 1:.1f}" width="7" height="{FS}" fill="{c["acento"]}" opacity="0">'
            f'<set attributeName="opacity" to="1" begin="{t_fin:.2f}s" fill="freeze"/>'
            f'<animate attributeName="opacity" values="1;0;1" dur="1.1s" begin="{t_fin:.2f}s" repeatCount="indefinite"/></rect>'
        )

    p.append("</svg>")
    return "\n".join(p) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--regen-ascii", action="store_true")
    ap.add_argument("--foto", default="foto.jpg")
    ap.add_argument("--estatico", action="store_true", help="SVG sin animacion para vista previa")
    args = ap.parse_args()

    if args.regen_ascii:
        generar_ascii(args.foto)

    est = obtener_estadisticas()
    for modo in ("dark", "light"):
        ruta = RAIZ / f"ascii_{modo}.txt"
        if not ruta.exists():
            sys.exit(f"Falta {ruta.name}. Ejecutar con --regen-ascii y la foto.")
        lineas = ruta.read_text(encoding="utf-8").splitlines()
        salida = RAIZ / (f"preview_{modo}.svg" if args.estatico else f"{modo}_mode.svg")
        salida.write_text(construir_svg(lineas, modo, est, animado=not args.estatico), encoding="utf-8")
        print("Escrito:", salida.name)


if __name__ == "__main__":
    main()