#!/usr/bin/env python3
import os
import sys
import tarfile
import shutil
import tempfile
import xml.etree.ElementTree as ET


BASE_DIR = "/home/Reneto/XFCEMenu"
THEMES_DIR = os.path.join(BASE_DIR, "themes")


def find_xml_with_content_type(directory):
    for root, dirs, files in os.walk(directory):
        for filename in files:
            if not filename.lower().endswith(".xml"):
                continue

            path = os.path.join(root, filename)

            try:
                tree = ET.parse(path)
                xml_root = tree.getroot()
                content_type = xml_root.attrib.get("type", "")
                if content_type:
                    return path, content_type
            except Exception:
                continue

    return None, None


def find_content_name(xml_path):
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        theme_node = root.find("theme")
        if theme_node is None:
            return None

        content_data = theme_node.find("ContentData")
        if content_data is None:
            return None

        return content_data.attrib.get("Name")
    except Exception:
        return None


def safe_copy_theme(source_dir, target_dir):
    if os.path.exists(target_dir):
        print(f"XFCEMenu: el tema ya existe, reemplazando: {target_dir}")
        shutil.rmtree(target_dir)

    shutil.copytree(source_dir, target_dir)


def import_theme(tar_path):
    if not os.path.isfile(tar_path):
        print(f"Archivo no encontrado: {tar_path}")
        return 1

    os.makedirs(THEMES_DIR, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="xfcemenu-import-") as temp_dir:
        try:
            with tarfile.open(tar_path, "r:*") as tar:
                tar.extractall(temp_dir)
        except Exception as e:
            print(f"No se pudo extraer el tema: {e}")
            return 1

        xml_path, content_type = find_xml_with_content_type(temp_dir)

        if not xml_path:
            print("No se encontró themedata.xml válido con <content type=\"...\">")
            return 1

        theme_root = os.path.dirname(xml_path)
        theme_name = find_content_name(xml_path)

        if not theme_name:
            theme_name = os.path.basename(theme_root)

        content_type = content_type.lower()

        if content_type == "menu":
            target_base = os.path.join(THEMES_DIR, "menus")
        elif content_type == "button":
            target_base = os.path.join(THEMES_DIR, "buttons")
        else:
            target_base = os.path.join(THEMES_DIR, "other")

        os.makedirs(target_base, exist_ok=True)

        target_dir = os.path.join(target_base, theme_name)

        safe_copy_theme(theme_root, target_dir)

        print("Tema importado correctamente.")
        print(f"Tipo: {content_type}")
        print(f"Nombre: {theme_name}")
        print(f"Ruta: {target_dir}")

    return 0


def main():
    if len(sys.argv) < 2:
        print("Uso:")
        print("  python3 importer.py tema.tar")
        print("  python3 importer.py tema.tar.gz")
        return 1

    return import_theme(sys.argv[1])


if __name__ == "__main__":
    sys.exit(main())