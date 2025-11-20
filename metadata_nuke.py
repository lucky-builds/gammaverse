import shutil
import zipfile
import tempfile
import os
from pathlib import Path
from typing import Tuple, Optional
import xml.etree.ElementTree as ET

from pypdf import PdfReader, PdfWriter

def nuke_pdf_metadata(input_path: Path, output_path: Path) -> bool:
    """
    Removes metadata from a PDF file.
    Returns True if successful.
    """
    try:
        reader = PdfReader(input_path)
        writer = PdfWriter()

        for page in reader.pages:
            writer.add_page(page)

        # Set empty metadata
        writer.add_metadata({
            "/Title": "",
            "/Author": "",
            "/Subject": "",
            "/Keywords": "",
            "/Creator": "",
            "/Producer": "",
            "/CreationDate": "",
            "/ModDate": "",
            "/Trapped": "/False"
        })

        with open(output_path, "wb") as f:
            writer.write(f)
        
        return True
    except Exception as e:
        print(f"Error nuking PDF metadata: {e}")
        return False

def nuke_pptx_metadata(input_path: Path, output_path: Path) -> bool:
    """
    Removes metadata from a PPTX file by modifying docProps/core.xml and app.xml.
    Returns True if successful.
    """
    try:
        # PPTX is a zip file. We need to copy it to a new location, 
        # but we can't just modify it in place easily with zipfile.
        # So we'll unzip to a temp dir, modify, and re-zip.
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Extract all
            with zipfile.ZipFile(input_path, 'r') as zip_ref:
                zip_ref.extractall(temp_path)
            
            # Modify core.xml
            core_xml_path = temp_path / "docProps" / "core.xml"
            if core_xml_path.exists():
                _scrub_xml(core_xml_path, [
                    "creator", "lastModifiedBy", "created", "modified", 
                    "title", "subject", "description", "keywords", "category"
                ])

            # Modify app.xml (often contains "Company", "Manager")
            app_xml_path = temp_path / "docProps" / "app.xml"
            if app_xml_path.exists():
                _scrub_xml(app_xml_path, ["Company", "Manager"])

            # Re-zip
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zip_out:
                for file_path in temp_path.rglob("*"):
                    if file_path.is_file():
                        arcname = file_path.relative_to(temp_path)
                        zip_out.write(file_path, arcname)
                        
        return True
    except Exception as e:
        print(f"Error nuking PPTX metadata: {e}")
        return False

def _scrub_xml(file_path: Path, tags_to_scrub: list[str]):
    """
    Helper to scrub specific tags from an XML file.
    It's a bit naive (just replaces text content), but effective for standard Office XML.
    """
    try:
        # We use a namespace-aware approach or just brute-force it since namespaces vary.
        # For simplicity and robustness against namespace variations in Office, 
        # let's parse, iterate, and clear text.
        
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        # Map of common namespaces in docProps
        namespaces = {
            'dc': 'http://purl.org/dc/elements/1.1/',
            'cp': 'http://schemas.openxmlformats.org/package/2006/metadata/core-properties',
            'dcterms': 'http://purl.org/dc/terms/'
        }
        
        # Helper to strip namespace for checking localname
        def get_local_name(tag):
            if '}' in tag:
                return tag.split('}', 1)[1]
            return tag

        for elem in root.iter():
            local_name = get_local_name(elem.tag)
            if local_name in tags_to_scrub:
                elem.text = ""
                # For dates, we might need a valid format if empty causes issues, 
                # but usually empty string or generic date is fine. 
                # Let's try empty first. If it breaks, we fix.
                if local_name in ["created", "modified"]:
                    elem.text = "1970-01-01T00:00:00Z"

        tree.write(file_path, encoding='UTF-8', xml_declaration=True)
        
    except Exception as e:
        print(f"Warning: Failed to scrub XML {file_path}: {e}")
