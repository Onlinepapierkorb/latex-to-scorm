import streamlit as st
import zipfile
from io import BytesIO
import re
import os
import fitz  # PyMuPDF für PDF-Verarbeitung
from docx import Document  # python-docx für DOCX-Verarbeitung
from pylatexenc.latex2text import LatexNodes2Text


def parse_latex_zip_to_html_with_images(latex_zip_bytes: bytes) -> (str, dict):
    """
    Erwartet ein ZIP, das mind. eine .tex-Datei und optional Bilddateien enthält.
    Sucht \includegraphics und wandelt sie zu <img>-Tags um.
    Gibt den HTML-String und ein Dict {bildname: bytes} zurück.
    """
    try:
        with zipfile.ZipFile(BytesIO(latex_zip_bytes), 'r') as zip_ref:
            file_list = zip_ref.namelist()
            # Suche nach .tex-Datei
            tex_files = [f for f in file_list if f.lower().endswith('.tex')]
            if not tex_files:
                raise ValueError("Keine .tex-Datei im ZIP gefunden.")

            # Nimm die erste .tex-Datei
            tex_file_name = tex_files[0]
            with zip_ref.open(tex_file_name, 'r') as f:
                latex_content = f.read().decode('utf-8', errors='replace')

            # Potentielle Bilddateien merken
            images_dict = {}
            for f in file_list:
                lower_f = f.lower()
                if lower_f.endswith(('.png', '.jpg', '.jpeg', '.gif')):
                    with zip_ref.open(f, 'r') as img_file:
                        images_dict[f] = img_file.read()

            # \includegraphics erkennen per Regex
            pattern = r'\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}'
            # Ersetze im Text die \includegraphics durch Platzhalter
            def replace_graphics(match):
                return f"[IMG::{match.group(1)}]"

            latex_content_modified = re.sub(pattern, replace_graphics, latex_content)

            # LaTeX -> (roher) Text
            text_converted = LatexNodes2Text().latex_to_text(latex_content_modified)
            # Zeilenumbrüche durch <br> ersetzen
            text_converted = text_converted.replace("\n", "<br>")

            # Platzhalter [IMG::datei] zu <img>-Tags
            def replace_img_placeholder(m):
                img_name = m.group(1).strip()
                # Prüfe, ob wir diesen Dateinamen im ZIP haben
                # (Manchmal ist in LaTeX kein .png/.jpg angegeben, hier sehr vereinfacht)
                found_key = None
                for k in images_dict.keys():
                    # Nur Dateiname ohne Pfad vergleichen:
                    if os.path.basename(k).lower() == img_name.lower():
                        found_key = k
                        break

                # Wenn nicht gefunden, probiere mit bekannten Extensions
                if not found_key:
                    for ext in [".png", ".jpg", ".jpeg", ".gif"]:
                        candidate = img_name + ext
                        for k in images_dict.keys():
                            if os.path.basename(k).lower() == candidate.lower():
                                found_key = k
                                break
                        if found_key:
                            break

                if found_key:
                    return f'<br><img src="{os.path.basename(found_key)}" alt="{os.path.basename(found_key)}"><br>'
                else:
                    return f'<br><strong>[Bild nicht gefunden: {img_name}]</strong><br>'

            final_html = re.sub(r'\[IMG::(.*?)\]', replace_img_placeholder, text_converted)

            # Einfache HTML-Hülle
            final_html = f"""<html>
<head><meta charset='utf-8'><title>Konvertiertes LaTeX</title></head>
<body>{final_html}</body>
</html>"""

            return final_html, images_dict
    except Exception as e:
        raise Exception("Fehler bei LaTeX-Verarbeitung (ZIP): " + str(e))


def parse_pdf_to_html_with_images(pdf_bytes: bytes) -> (str, dict):
    """
    Extrahiert aus einem PDF den Text (seiteweise) und die Bilder.
    Setzt alles in HTML um, Bilder werden am Seitenende angehängt.
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        all_text = []
        images_dict = {}
        image_counter = 1

        for page_index in range(len(doc)):
            page = doc[page_index]
            text = page.get_text("text").replace("\n", "<br>")
            all_text.append(f"<h3>Seite {page_index+1}</h3>")
            all_text.append(text)

            # Bilder extrahieren
            image_list = page.get_images(full=True)
            for img in image_list:
                xref = img[0]
                base_image = doc.extract_image(xref)
                img_bytes = base_image["image"]
                img_ext = base_image["ext"]
                img_filename = f"pdf_image_{page_index+1}_{image_counter}.{img_ext}"
                images_dict[img_filename] = img_bytes
                # Wir hängen das Bild direkt unten an
                all_text.append(f'<br><img src="{img_filename}" alt="Seite{page_index+1}-Bild{image_counter}"><br>')
                image_counter += 1

        doc.close()
        final_html = "<html><head><meta charset='utf-8'><title>Konvertiertes PDF</title></head><body>"
        final_html += "".join(all_text)
        final_html += "</body></html>"

        return final_html, images_dict
    except Exception as e:
        raise Exception("Fehler bei PDF-Verarbeitung: " + str(e))


def parse_docx_to_html_with_images(docx_bytes: bytes) -> (str, dict):
    """
    Liest eine DOCX-Datei ein, extrahiert Text (Paragraphen) und Bilder aus 'word/media'.
    Hängt die Bilder (der Einfachheit halber) am Ende des Textes an.
    """
    try:
        # Temporär abspeichern
        temp_path = "temp_upload.docx"
        with open(temp_path, "wb") as f:
            f.write(docx_bytes)

        doc = Document(temp_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        # Als HTML mit <br> verketten
        text_html = "<br>".join(paragraphs)

        # Bilder extrahieren (aus dem Zip-Container)
        images_dict = {}
        with zipfile.ZipFile(BytesIO(docx_bytes), 'r') as zip_ref:
            media_files = [f for f in zip_ref.namelist() if f.lower().startswith("word/media/")]
            for i, mf in enumerate(media_files, start=1):
                with zip_ref.open(mf, 'r') as img_file:
                    img_bytes = img_file.read()
                ext = os.path.splitext(mf)[1]  # z.B. .png, .jpg
                filename = f"docx_image_{i}{ext}"
                images_dict[filename] = img_bytes

        final_html = "<html><head><meta charset='utf-8'><title>Konvertiertes DOCX</title></head><body>"
        final_html += text_html

        # Bilder am Ende anfügen
        if images_dict:
            final_html += "<hr><h4>Eingebettete Bilder:</h4>"
            for img_name in images_dict:
                final_html += f'<br><img src="{img_name}" alt="{img_name}"><br>'

        final_html += "</body></html>"
        return final_html, images_dict
    except Exception as e:
        raise Exception("Fehler bei DOCX-Verarbeitung: " + str(e))


def parse_single_tex_to_html(latex_bytes: bytes) -> (str, dict):
    """
    Wenn nur eine einzelne .tex-Datei (ohne ZIP) hochgeladen wird,
    dann konvertieren wir den Text. Bilder können hier NICHT automatisch
    eingebunden werden, da sie nicht im ZIP liegen.
    """
    try:
        latex_content = latex_bytes.decode('utf-8', errors='replace')
        text_converted = LatexNodes2Text().latex_to_text(latex_content)
        text_converted = text_converted.replace("\n", "<br>")
        final_html = f"<html><head><meta charset='utf-8'><title>Konvertiertes LaTeX</title></head><body>{text_converted}</body></html>"
        return final_html, {}
    except Exception as e:
        raise Exception("Fehler bei einzelner .tex-Datei: " + str(e))


def create_scorm_package(html_content: str, additional_files: dict = None) -> bytes:
    """
    Erzeugt ein SCORM-1.2-Paket:
    - index.html + imsmanifest.xml + evtl. Bilder (aus additional_files).
    """
    if additional_files is None:
        additional_files = {}

    manifest = """<?xml version="1.0" encoding="UTF-8"?>
<manifest identifier="com.example.scorm" version="1.2">
  <organizations default="ORG-1">
    <organization identifier="ORG-1">
      <title>Konvertiertes Dokument</title>
      <item identifier="ITEM-1" identifierref="RES-1">
        <title>Startseite</title>
      </item>
    </organization>
  </organizations>
  <resources>
    <resource identifier="RES-1" type="webcontent" href="index.html">
      <file href="index.html"/>
    </resource>
  </resources>
</manifest>
"""

    html_wrapper = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Konvertiertes Dokument</title>
</head>
<body>
    {html_content}
</body>
</html>
"""

    bytes_io = BytesIO()
    try:
        with zipfile.ZipFile(bytes_io, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("index.html", html_wrapper)
            zf.writestr("imsmanifest.xml", manifest)
            # Zusätzliche Dateien, z.B. Bilder
            for filename, filedata in additional_files.items():
                zf.writestr(filename, filedata)
        return bytes_io.getvalue()
    except Exception as e:
        raise Exception("Fehler beim Erstellen des SCORM-Pakets: " + str(e))


def parse_file_to_html_with_images(file_bytes: bytes, filename: str) -> (str, dict):
    """
    Ermittelt anhand des Dateinamens, um welchen Typ es sich handelt,
    und ruft die passende Parsing-Funktion auf.
    Gibt (html_content, images_dict) zurück.
    """
    lower_name = filename.lower()

    if lower_name.endswith(".pdf"):
        return parse_pdf_to_html_with_images(file_bytes)
    elif lower_name.endswith(".docx"):
        return parse_docx_to_html_with_images(file_bytes)
    elif lower_name.endswith(".zip"):
        # Wir gehen davon aus, dass es sich um ein LaTeX-Projekt im ZIP handelt
        return parse_latex_zip_to_html_with_images(file_bytes)
    elif lower_name.endswith(".tex"):
        # Einzelne .tex-Datei (ohne Bilder)
        return parse_single_tex_to_html(file_bytes)
    else:
        raise ValueError("Dateiformat nicht unterstützt. Bitte PDF, DOCX, ZIP oder TEX hochladen.")


# ------------------------------------------------------------------------------------
# STREAMLIT-APP
# ------------------------------------------------------------------------------------
st.title("Einfacher Konverter zu SCORM: PDF, DOCX, LaTeX (ZIP/TEX)")

uploaded_file = st.file_uploader(
    "Bitte eine PDF, eine DOCX, eine .tex oder ein LaTeX-ZIP hochladen.",
    type=["pdf", "docx", "zip", "tex"]
)

if uploaded_file is not None:
    try:
        file_content = uploaded_file.read()
        # Automatische Erkennung und Konvertierung
        st.info(f"Verarbeite {uploaded_file.name} ...")
        html_result, images = parse_file_to_html_with_images(file_content, uploaded_file.name)
        st.success("Datei erfolgreich zu HTML konvertiert.")

        # SCORM-Paket erstellen
        scorm_data = create_scorm_package(html_result, images)

        st.download_button(
            label="SCORM-Paket herunterladen",
            data=scorm_data,
            file_name="scorm_package.zip",
            mime="application/zip"
        )
    except Exception as e:
        st.error(f"Fehler: {e}")


# Optional: Erklärungsknopf
if st.button("Wie funktioniert der Code?"):
    st.markdown("""
    **Ablauf:**

    1. **Upload**  
       - Du lädst eine Datei hoch (PDF, DOCX, ZIP oder TEX).

    2. **Erkennung Dateityp**  
       - Anhand der Dateiendung wird entschieden, welche Parsing-Funktion aufgerufen wird:
         - `.pdf` -> PDF wird mit **PyMuPDF** zerlegt (Seite für Seite Text + Bilder).
         - `.docx` -> Word wird mit **python-docx** ausgelesen (Paragraphen + Bilder aus `word/media`).
         - `.zip` -> Wird als LaTeX-Projekt interpretiert (`.tex` + Bilder).  
           Hier werden `\includegraphics` gesucht und in `<img>`-Tags umgewandelt.
         - `.tex` -> Eine reine `.tex`-Datei ohne Bildunterstützung (da keine Bilddateien bereitstehen).

    3. **Erzeugung des HTML**  
       - Der Text wird in einen einfachen HTML-Body geschrieben.
       - Gefundene Bilder werden als `<img>`-Tag eingefügt.

    4. **SCORM-Paket**  
       - Ein simples `imsmanifest.xml` + `index.html` + Bilder werden in ein ZIP gepackt.
       - Dieses ZIP kann als SCORM-Paket in einer entsprechenden LMS-Umgebung genutzt werden.

    > **LaTeX-Hinweis**  
    > Wenn Bilder benötigt werden, muss die `.tex`-Datei mit den Bildern in einem ZIP hochgeladen werden.  
    > Bei einer einzelnen `.tex`-Datei können keine zusätzlichen Bilddateien verarbeitet werden.

    **Viel Erfolg beim Konvertieren!**
    """)
