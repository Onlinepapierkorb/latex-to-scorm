import streamlit as st
import zipfile
import pypandoc
pypandoc.download_pandoc()
from io import BytesIO

def convert_latex_to_html(latex_content: str) -> str:
    """
    Konvertiert den LaTeX-Text in HTML mithilfe von Pandoc.
    Dabei werden gängige LaTeX-Befehle (z. B. \newpage, \addsec) in entsprechende HTML-Elemente umgewandelt.
    """
    try:
        html_content = pypandoc.convert_text(latex_content, 'html', format='latex')
        return html_content
    except Exception as e:
        raise Exception("Fehler bei der LaTeX-zu-HTML-Konvertierung: " + str(e))

def create_scorm_package(html_content: str) -> bytes:
    """
    Erstellt ein SCORM-kompatibles Paket:
    - Das HTML wird in eine index.html eingebettet.
    - Eine imsmanifest.xml definiert die Ressource.
    - Beide Dateien werden in einer ZIP-Datei verpackt.
    """
    try:
        manifest = """<?xml version="1.0" encoding="UTF-8"?>
<manifest identifier="com.example.scorm" version="1.2">
  <organizations default="ORG-1">
    <organization identifier="ORG-1">
      <title>LaTeX zu SCORM Konverter</title>
      <item identifier="ITEM-1" identifierref="RES-1">
        <title>Hauptseite</title>
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
        # Ein einfaches HTML-Gerüst, in das die konvertierten Inhalte eingebettet werden.
        html_wrapper = f"""<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8">
    <title>Konvertiertes LaTeX-Dokument</title>
  </head>
  <body>
    {html_content}
  </body>
</html>
"""
        # Erstellen der ZIP-Datei im Arbeitsspeicher
        bytes_io = BytesIO()
        with zipfile.ZipFile(bytes_io, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr("index.html", html_wrapper)
            zip_file.writestr("imsmanifest.xml", manifest)
        return bytes_io.getvalue()
    except Exception as e:
        raise Exception("Fehler bei der Erstellung des SCORM-Pakets: " + str(e))

# Streamlit-Benutzeroberfläche
st.title("LaTeX zu SCORM Konverter")
st.write("Laden Sie Ihre LaTeX-Datei (.tex) hoch, um ein SCORM-kompatibles Paket zu erstellen.")

uploaded_file = st.file_uploader("LaTeX-Datei hochladen", type=["tex"])

if uploaded_file is not None:
    try:
        # Einlesen und Umwandeln in einen String
        latex_content = uploaded_file.read().decode('utf-8')
        
        # Konvertierung von LaTeX zu HTML
        html_content = convert_latex_to_html(latex_content)
        st.success("LaTeX wurde erfolgreich in HTML konvertiert.")
        
        # Erstellung des SCORM-Pakets
        scorm_zip = create_scorm_package(html_content)
        st.download_button(
            label="SCORM-Paket herunterladen",
            data=scorm_zip,
            file_name="scorm_package.zip",
            mime="application/zip"
        )
    except Exception as error:
        st.error(f"Ein Fehler ist aufgetreten: {error}")

# Erklärung des Codes
if st.button("Wie funktioniert der Code?"):
    st.markdown("""
    **Funktionsweise der Anwendung:**

    1. **LaTeX-Datei hochladen**  
       - Der Benutzer kann eine `.tex`-Datei hochladen.
    
    2. **Konvertierung von LaTeX nach HTML**  
       - Der LaTeX-Inhalt wird mit `pypandoc.convert_text()` in HTML umgewandelt.
       - Dabei werden gängige LaTeX-Elemente (wie newpage oder addsec) in HTML übertragen.

    3. **Erstellung des SCORM-Pakets**  
       - Das HTML wird als `index.html` gespeichert.
       - Eine SCORM-konforme `imsmanifest.xml` wird generiert, die die Struktur des Pakets definiert.
       - Beide Dateien werden in einer ZIP-Datei gebündelt.

    4. **Download der SCORM-Datei**  
       - Die fertige ZIP-Datei kann als SCORM-Paket heruntergeladen werden.

    **Verwendete Technologien:**
    - **Streamlit** für die Benutzeroberfläche
    - **pypandoc** für die LaTeX-zu-HTML-Konvertierung
    - **zipfile** für das Erstellen des SCORM-Pakets
    """)
