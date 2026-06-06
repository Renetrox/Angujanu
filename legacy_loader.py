#!/usr/bin/env python3
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class LegacyButton:
    name: str = ""
    markup: str = ""
    text_x: int = 0
    text_y: int = 0
    image: str = ""
    button_icon: str = ""
    button_icon_sel: str = ""
    x: int = 0
    y: int = 0
    submenu: int = 0
    command: str = ""
    close_menu: int = 1
    execute_on_hover: int = 0
    icon: str = ""


@dataclass
class LegacyLabel:
    name: str = ""
    markup: str = ""
    x: int = 0
    y: int = 0
    command: str = ""


@dataclass
class IconSettings:
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    inset_x: int = 0
    inset_y: int = 0
    inset_width: int = 0
    inset_height: int = 0


@dataclass
class ProgramListSettings:
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    only_recent: int = 0
    only_favs: int = 0


@dataclass
class SearchBarSettings:
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    widget: str = "None"
    widget_name: str = ""
    initial_text: str = ""
    inset_x: int = 0
    inset_y: int = 0
    style: str = ""
    background: str = ""


@dataclass
class LegacyMenuTheme:
    name: str = "Unknown"
    author: str = ""
    version: str = ""
    copyright: str = ""
    theme_dir: str = ""
    width: int = 380
    height: int = 497
    background: str = ""
    icon_settings: Optional[IconSettings] = None
    program_list: Optional[ProgramListSettings] = None
    search_bar: Optional[SearchBarSettings] = None
    buttons: List[LegacyButton] = field(default_factory=list)
    labels: List[LegacyLabel] = field(default_factory=list)


def _int_attr(node, name: str, default: int = 0) -> int:
    if node is None:
        return default

    try:
        value = node.attrib.get(name, default)
        return int(value)
    except (ValueError, TypeError):
        return default


def _str_attr(node, name: str, default: str = "") -> str:
    if node is None:
        return default

    value = node.attrib.get(name, default)

    if value is None:
        return default

    return str(value)


def _find_child(parent, tag_name: str):
    """
    Busca un hijo directo ignorando mayúsculas/minúsculas.
    """
    if parent is None:
        return None

    tag_name = tag_name.lower()

    for child in list(parent):
        if child.tag.lower() == tag_name:
            return child

    return None


def _find_children(parent, tag_name: str):
    """
    Busca hijos directos ignorando mayúsculas/minúsculas.
    """
    if parent is None:
        return []

    tag_name = tag_name.lower()

    return [child for child in list(parent) if child.tag.lower() == tag_name]


def _read_legacy_xml_text(xml_path: str) -> str:
    """
    Muchos temas viejos de GnoMenu usan líneas con # como comentario,
    pero eso no es XML válido. Las limpiamos antes de parsear.
    """
    with open(xml_path, "r", encoding="utf-8", errors="replace") as f:
        raw = f.read()

    cleaned_lines = []

    for line in raw.splitlines():
        stripped = line.lstrip()

        if stripped.startswith("#"):
            continue

        cleaned_lines.append(line)

    text = "\n".join(cleaned_lines)

    # Limpieza suave para XMLs legacy con espacios raros antes de '='.
    text = re.sub(r"\s+=\s+", "=", text)

    return text


def find_theme_xml(theme_dir: str) -> Optional[str]:
    """
    Busca el XML principal del tema.
    GnoMenu normalmente usa themedata.xml.
    """
    preferred = [
        "themedata.xml",
        "theme.xml",
        "menu.xml",
        "button.xml",
    ]

    for filename in preferred:
        path = os.path.join(theme_dir, filename)
        if os.path.isfile(path):
            return path

    try:
        for filename in os.listdir(theme_dir):
            if filename.lower().endswith(".xml"):
                return os.path.join(theme_dir, filename)
    except FileNotFoundError:
        return None

    return None


def load_menu_theme(theme_dir: str) -> LegacyMenuTheme:
    xml_path = find_theme_xml(theme_dir)

    if not xml_path:
        raise FileNotFoundError(f"No se encontró XML de tema en: {theme_dir}")

    xml_text = _read_legacy_xml_text(xml_path)

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise ValueError(f"XML inválido en {xml_path}: {e}")

    content_type = root.attrib.get("type", "")

    if content_type.lower() != "menu":
        raise ValueError(f"El tema no es de tipo Menu: {content_type}")

    theme_node = _find_child(root, "theme")

    if theme_node is None:
        raise ValueError("XML inválido: no contiene <theme>")

    menu = LegacyMenuTheme()
    menu.theme_dir = theme_dir

    # En los XML de GnoMenu, ContentData suele estar directo dentro de <content>,
    # no dentro de <theme>.
    content_data = _find_child(root, "ContentData")

    if content_data is None:
        content_data = _find_child(theme_node, "ContentData")

    if content_data is not None:
        menu.name = _str_attr(content_data, "Name", os.path.basename(theme_dir))
        menu.author = _str_attr(content_data, "Author", "")
        menu.version = _str_attr(content_data, "Version", "")
        menu.copyright = _str_attr(content_data, "Copyright", "")
    else:
        menu.name = os.path.basename(theme_dir)

    background = _find_child(theme_node, "Background")
    if background is not None:
        menu.background = _str_attr(background, "Image", "")

    dimensions = _find_child(theme_node, "WindowDimensions")
    if dimensions is not None:
        menu.width = _int_attr(dimensions, "Width", 380)
        menu.height = _int_attr(dimensions, "Height", 497)

    icon_settings = _find_child(theme_node, "IconSettings")
    if icon_settings is not None:
        menu.icon_settings = IconSettings(
            x=_int_attr(icon_settings, "X", 0),
            y=_int_attr(icon_settings, "Y", 0),
            width=_int_attr(icon_settings, "Width", 0),
            height=_int_attr(icon_settings, "Height", 0),
            inset_x=_int_attr(icon_settings, "InsetX", 0),
            inset_y=_int_attr(icon_settings, "InsetY", 0),
            inset_width=_int_attr(icon_settings, "InsetWidth", 0),
            inset_height=_int_attr(icon_settings, "InsetHeight", 0),
        )

    program_settings = _find_child(theme_node, "ProgramListSettings")
    if program_settings is not None:
        menu.program_list = ProgramListSettings(
            x=_int_attr(program_settings, "X", 0),
            y=_int_attr(program_settings, "Y", 0),
            width=_int_attr(program_settings, "Width", 0),
            height=_int_attr(program_settings, "Height", 0),
            only_recent=_int_attr(program_settings, "OnlyShowRecentApps", 0),
            only_favs=_int_attr(program_settings, "OnlyShowFavs", 0),
        )

    search_settings = _find_child(theme_node, "SearchBarSettings")
    if search_settings is not None:
        menu.search_bar = SearchBarSettings(
            x=_int_attr(search_settings, "X", 0),
            y=_int_attr(search_settings, "Y", 0),
            width=_int_attr(search_settings, "Width", 0),
            height=_int_attr(search_settings, "Height", 0),
            widget=_str_attr(search_settings, "Widget", "None"),
            widget_name=_str_attr(search_settings, "WidgetName", ""),
            initial_text=_str_attr(search_settings, "InitialText", ""),
            inset_x=_int_attr(search_settings, "InsetX", 0),
            inset_y=_int_attr(search_settings, "InsetY", 0),
            style=_str_attr(search_settings, "style", ""),
            background=_str_attr(search_settings, "Background", ""),
        )

    for button_node in _find_children(theme_node, "Button"):
        button = LegacyButton(
            name=_str_attr(button_node, "Name", ""),
            markup=_str_attr(button_node, "Markup", ""),
            text_x=_int_attr(button_node, "TextX", 0),
            text_y=_int_attr(button_node, "TextY", 0),
            image=_str_attr(button_node, "Image", ""),
            button_icon=_str_attr(button_node, "ButtonIcon", ""),
            button_icon_sel=_str_attr(button_node, "ButtonIconSel", ""),
            x=_int_attr(button_node, "ButtonX", 0),
            y=_int_attr(button_node, "ButtonY", 0),
            submenu=_int_attr(button_node, "SubMenu", 0),
            command=_str_attr(button_node, "Command", ""),
            close_menu=_int_attr(button_node, "CloseMenu", 1),
            execute_on_hover=_int_attr(button_node, "ExecuteOnHover", 0),
            icon=_str_attr(button_node, "Icon", ""),
        )

        menu.buttons.append(button)

    for label_node in _find_children(theme_node, "Label"):
        label = LegacyLabel(
            name=_str_attr(label_node, "Name", ""),
            markup=_str_attr(label_node, "Markup", ""),
            x=_int_attr(label_node, "LabelX", 0),
            y=_int_attr(label_node, "LabelY", 0),
            command=_str_attr(label_node, "Command", ""),
        )

        menu.labels.append(label)

    print("XFCEMenu: tema cargado")
    print(f"  Nombre: {menu.name}")
    print(f"  Autor: {menu.author}")
    print(f"  Tamaño: {menu.width}x{menu.height}")
    print(f"  Fondo: {menu.background}")

    if menu.icon_settings:
        print(
            "  IconSettings: "
            f"{menu.icon_settings.x},{menu.icon_settings.y} "
            f"{menu.icon_settings.width}x{menu.icon_settings.height} "
            f"inset={menu.icon_settings.inset_x},{menu.icon_settings.inset_y} "
            f"{menu.icon_settings.inset_width}x{menu.icon_settings.inset_height}"
        )
    else:
        print("  IconSettings: no definido")

    print(f"  Botones: {len(menu.buttons)}")
    print(f"  Labels: {len(menu.labels)}")

    return menu
