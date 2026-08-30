import re
import urllib.request
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import urljoin


BASE_URL = "https://www.mfemediaforeurope.com"

PAGINA_PRINCIPAL = (
    "https://www.mfemediaforeurope.com/es/"
    "medios-de-comunicacion/"
    "comunicados-de-prensa/"
)

ARCHIVO_RSS = "mfe.xml"

MESES = {
    "ENE": 1,
    "FEB": 2,
    "MAR": 3,
    "ABR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AGO": 8,
    "SEP": 9,
    "SEPT": 9,
    "OCT": 10,
    "NOV": 11,
    "DIC": 12,
}


def limpiar_texto(texto):
    return re.sub(
        r"\s+",
        " ",
        texto or "",
    ).strip()


def descargar_pagina(url):
    solicitud = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "es-ES,es;q=0.9",
            "Cache-Control": "no-cache",
        },
    )

    with urllib.request.urlopen(
        solicitud,
        timeout=60,
    ) as respuesta:
        return respuesta.read()


def convertir_fecha(texto):
    texto = limpiar_texto(texto).upper()

    coincidencia = re.search(
        r"\b("
        r"ENE|FEB|MAR|ABR|MAY|JUN|JUL|"
        r"AGO|SEP|SEPT|OCT|NOV|DIC"
        r")\s+(\d{1,2})\s+(\d{4})"
        r"(?:\s+(\d{1,2}):(\d{2}))?",
        texto,
    )

    if not coincidencia:
        return None

    mes = MESES[coincidencia.group(1)]
    dia = int(coincidencia.group(2))
    anio = int(coincidencia.group(3))

    if coincidencia.group(4):
        hora = int(coincidencia.group(4))
    else:
        hora = 8

    if coincidencia.group(5):
        minuto = int(coincidencia.group(5))
    else:
        minuto = 0

    try:
        return datetime(
            anio,
            mes,
            dia,
            hora,
            minuto,
            tzinfo=timezone.utc,
        )

    except ValueError:
        return None


def buscar_contenedor(encabezado):
    contenedor = encabezado

    for _ in range(8):
        if contenedor is None:
            break

        texto = limpiar_texto(
            contenedor.get_text(" ", strip=True)
        )

        enlace_descarga = contenedor.find(
            "a",
            href=True,
            string=re.compile(
                r"descargar",
                re.IGNORECASE,
            ),
        )

        tiene_fecha = re.search(
            r"\b("
            r"ENE|FEB|MAR|ABR|MAY|JUN|JUL|"
            r"AGO|SEP|SEPT|OCT|NOV|DIC"
            r")\s+\d{1,2}\s+\d{4}\b",
            texto.upper(),
        )

        if enlace_descarga and tiene_fecha:
            return contenedor

        contenedor = contenedor.parent

    return None


def obtener_noticias():
    contenido = descargar_pagina(
        PAGINA_PRINCIPAL
    )

    soup = BeautifulSoup(
        contenido,
        "html.parser",
    )

    noticias = []
    enlaces_vistos = set()

    encabezados = soup.find_all(
        ["h4", "h5", "h6"]
    )

    for encabezado in encabezados:
        titulo = limpiar_texto(
            encabezado.get_text(" ", strip=True)
        )

        if len(titulo) < 20:
            continue

        contenedor = buscar_contenedor(
            encabezado
        )

        if contenedor is None:
            continue

        enlace = contenedor.find(
            "a",
            href=True,
            string=re.compile(
                r"descargar",
                re.IGNORECASE,
            ),
        )

        if enlace is None:
            continue

        href = limpiar_texto(
            enlace.get("href", "")
        )

        if not href:
            continue

        if href.lower().startswith("javascript:"):
            continue

        url = urljoin(
            BASE_URL,
            href,
        )

        url = url.split("#")[0]

        if url in enlaces_vistos:
            continue

        texto_contenedor = limpiar_texto(
            contenedor.get_text(" ", strip=True)
        )

        fecha = convertir_fecha(
            texto_contenedor
        )

        enlaces_vistos.add(url)

        noticias.append(
            {
                "titulo": titulo,
                "url": url,
                "fecha": fecha,
                "descripcion": (
                    "Comunicado de prensa oficial "
                    "publicado por MFE-MEDIAFOREUROPE."
                ),
            }
        )

        print(
            f"Comunicado encontrado: {titulo}"
        )

    if not noticias:
        raise RuntimeError(
            "No se encontraron comunicados "
            "de MFE-MEDIAFOREUROPE"
        )

    noticias.sort(
        key=lambda noticia: (
            noticia["fecha"]
            or datetime(
                1970,
                1,
                1,
                tzinfo=timezone.utc,
            )
        ),
        reverse=True,
    )

    return noticias


def crear_rss(noticias):
    rss = ET.Element(
        "rss",
        {
            "version": "2.0",
            "xmlns:atom": (
                "http://www.w3.org/2005/Atom"
            ),
        },
    )

    canal = ET.SubElement(
        rss,
        "channel",
    )

    ET.SubElement(
        canal,
        "title",
    ).text = (
        "MFE-MEDIAFOREUROPE – "
        "Comunicados de prensa"
    )

    ET.SubElement(
        canal,
        "link",
    ).text = PAGINA_PRINCIPAL

    ET.SubElement(
        canal,
        "description",
    ).text = (
        "Últimos comunicados oficiales "
        "publicados por MFE-MEDIAFOREUROPE"
    )

    ET.SubElement(
        canal,
        "language",
    ).text = "es-es"

    ET.SubElement(
        canal,
        "ttl",
    ).text = "60"

    ET.SubElement(
        canal,
        "{http://www.w3.org/2005/Atom}link",
        {
            "href": (
                "https://raw.githubusercontent.com/"
                "plis2100/rss-mfe/main/mfe.xml"
            ),
            "rel": "self",
            "type": "application/rss+xml",
        },
    )

    ahora = datetime.now(timezone.utc)

    ET.SubElement(
        canal,
        "lastBuildDate",
    ).text = format_datetime(ahora)

    for noticia in noticias:
        elemento = ET.SubElement(
            canal,
            "item",
        )

        ET.SubElement(
            elemento,
            "title",
        ).text = noticia["titulo"]

        ET.SubElement(
            elemento,
            "link",
        ).text = noticia["url"]

        ET.SubElement(
            elemento,
            "guid",
            {"isPermaLink": "true"},
        ).text = noticia["url"]

        ET.SubElement(
            elemento,
            "description",
        ).text = noticia["descripcion"]

        ET.SubElement(
            elemento,
            "source",
            {"url": PAGINA_PRINCIPAL},
        ).text = "MFE-MEDIAFOREUROPE"

        if noticia["fecha"]:
            ET.SubElement(
                elemento,
                "pubDate",
            ).text = format_datetime(
                noticia["fecha"]
            )

    arbol = ET.ElementTree(rss)

    ET.indent(
        arbol,
        space="  ",
    )

    arbol.write(
        ARCHIVO_RSS,
        encoding="utf-8",
        xml_declaration=True,
    )


def validar_rss():
    archivo = Path(ARCHIVO_RSS)

    if not archivo.exists():
        raise RuntimeError(
            "No se creó mfe.xml"
        )

    if archivo.stat().st_size < 500:
        raise RuntimeError(
            "mfe.xml está vacío"
        )

    raiz = ET.parse(archivo).getroot()

    elementos = raiz.findall(
        "./channel/item"
    )

    if not elementos:
        raise RuntimeError(
            "La RSS de MFE no contiene comunicados"
        )

    return len(elementos)


def main():
    noticias = obtener_noticias()

    crear_rss(noticias)

    cantidad = validar_rss()

    print(
        f"RSS de MFE creada correctamente: "
        f"{cantidad} comunicados"
    )

    print(
        f"Último comunicado: "
        f"{noticias[0]['titulo']}"
    )

    print(
        f"Archivo generado: {ARCHIVO_RSS}"
    )


if __name__ == "__main__":
    main()
