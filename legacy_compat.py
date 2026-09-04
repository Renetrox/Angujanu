#!/usr/bin/env python3
"""Runtime compatibility helpers for legacy GnoMenu menu themes.

The original XML loader in Angujanu intentionally stays small. This module
enriches the parsed theme with legacy fields that older GnoMenu themes used,
without changing the public dataclasses or requiring theme conversion.
"""

import os
import re
import struct
import xml.etree.ElementTree as ET
from types import SimpleNamespace


def _int_attr(node, name, default=0):
    if node is None:
        return default
    try:
        return int(node.attrib.get(name, default))
    except (TypeError, ValueError):
        return default


def _str_attr(node, name, default=""):
    if node is None:
        return default
    value = node.attrib.get(name, default)
    return default if value is None else str(value)


def _read_xml_text(path):
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        raw = handle.read()

    lines = []
    for line in raw.splitlines():
        if line.lstrip().startswith("#"):
            continue
        lines.append(line)

    text = "\n".join(lines)
    text = re.sub(r"\s+=\s+", "=", text)
    text = re.sub(r"(/>)\\", r"\1", text)
    return text


def _direct_children(parent, tag_name):
    if parent is None:
        return []
    wanted = tag_name.lower()
    return [child for child in list(parent) if str(child.tag).lower() == wanted]


def _direct_child(parent, tag_name):
    children = _direct_children(parent, tag_name)
    return children[0] if children else None


def _select_theme_node(root):
    """Use the same theme block as the current base loader: the first one."""
    themes = _direct_children(root, "theme")
    return themes[0] if themes else None


def _png_size(path):
    try:
        with open(path, "rb") as handle:
            header = handle.read(24)
        if len(header) >= 24 and header[:8] == b"\x89PNG\r\n\x1a\n":
            width, height = struct.unpack(">II", header[16:24])
            if width > 0 and height > 0:
                return int(width), int(height)
    except Exception:
        pass
    return None


def _gif_size(path):
    try:
        with open(path, "rb") as handle:
            header = handle.read(10)
        if len(header) >= 10 and header[:6] in (b"GIF87a", b"GIF89a"):
            width, height = struct.unpack("<HH", header[6:10])
            if width > 0 and height > 0:
                return int(width), int(height)
    except Exception:
        pass
    return None


def _svg_size(path):
    try:
        root = ET.parse(path).getroot()
        width = str(root.attrib.get("width", "")).strip().lower().replace("px", "")
        height = str(root.attrib.get("height", "")).strip().lower().replace("px", "")
        if width and height:
            return int(float(width)), int(float(height))

        viewbox = root.attrib.get("viewBox") or root.attrib.get("viewbox")
        if viewbox:
            values = [float(value) for value in re.split(r"[,\s]+", viewbox.strip()) if value]
            if len(values) == 4 and values[2] > 0 and values[3] > 0:
                return int(round(values[2])), int(round(values[3]))
    except Exception:
        pass
    return None


def image_size(path):
    if not path or not os.path.isfile(path):
        return None

    lower = path.lower()
    if lower.endswith(".png"):
        return _png_size(path)
    if lower.endswith((".gif", ".gif87a", ".gif89a")):
        return _gif_size(path)
    if lower.endswith(".svg"):
        return _svg_size(path)

    # Most original GnoMenu menu skins are PNG. Try PNG even when the extension
    # is unusual before giving up.
    return _png_size(path)


def _theme_image_path(theme, filename):
    filename = str(filename or "").strip()
    if not filename:
        return ""
    if os.path.isabs(filename):
        return filename
    return os.path.join(getattr(theme, "theme_dir", "") or "", filename)


def _enrich_dimensions(theme):
    """GnoMenu preferred Background image dimensions over WindowDimensions."""
    background = getattr(theme, "background", "") or ""
    size = image_size(_theme_image_path(theme, background))
    if not size:
        return

    width, height = size
    theme.width = width
    theme.height = height
    setattr(theme, "_angujanu_dimensions_from_background", True)


def _enrich_capabilities(theme, theme_node):
    node = _direct_child(theme_node, "Capabilities")
    if node is None:
        return

    theme.capabilities = SimpleNamespace(
        has_search=_int_attr(node, "HasSearch", 1),
        has_icon=_int_attr(node, "HasIcon", 1),
        has_fade_transition=_int_attr(node, "HasFadeTransition", 0),
    )


def _enrich_search(theme, theme_node):
    node = _direct_child(theme_node, "SearchBarSettings")
    search = getattr(theme, "search_bar", None)
    if node is None or search is None:
        return

    search.text_color = _str_attr(node, "TextColor", "#000000")
    search.back_color = _str_attr(node, "BackColor", "#FFFFFF")
    search.border_color = _str_attr(node, "BorderColor", "#000000")
    search.round_angle = _int_attr(node, "RoundAngle", 0)

    if not getattr(search, "style", ""):
        search.style = _str_attr(node, "Style", _str_attr(node, "style", ""))


def _enrich_images(theme, theme_node):
    images = []
    for node in _direct_children(theme_node, "Image"):
        images.append(
            SimpleNamespace(
                name=_str_attr(node, "Name", ""),
                image=_str_attr(node, "Image", ""),
                x=_int_attr(node, "ImageX", 0),
                y=_int_attr(node, "ImageY", 0),
            )
        )
    theme.images = images


def _enrich_buttons(theme, theme_node):
    nodes = _direct_children(theme_node, "Button")
    buttons = list(getattr(theme, "buttons", []) or [])

    for button, node in zip(buttons, nodes):
        button.text_alignment = _int_attr(node, "TextAlignment", 0)
        button.button_icon_x = _int_attr(node, "ButtonIconX", 0)
        button.button_icon_y = _int_attr(node, "ButtonIconY", 0)
        button.button_icon_size = _int_attr(node, "ButtonIconSize", 0)

        # Preserve both layers exactly as the old MenuButton widget did:
        # ImageBack is the permanent background; Image is the hover overlay.
        button.image_back = _str_attr(node, "ImageBack", getattr(button, "image_back", ""))
        button.image = _str_attr(node, "Image", getattr(button, "image", ""))


def _enrich_tabs(theme, theme_node):
    nodes = _direct_children(theme_node, "Tab")
    tabs = list(getattr(theme, "tabs", []) or [])

    for tab, node in zip(tabs, nodes):
        # GnoMenu accepted deprecated IconX/IconY/IconSize aliases.
        if "TabIconX" not in node.attrib and "IconX" in node.attrib:
            tab.tab_icon_x = _int_attr(node, "IconX", 0)
        if "TabIconY" not in node.attrib and "IconY" in node.attrib:
            tab.tab_icon_y = _int_attr(node, "IconY", 0)
        if "TabIconSize" not in node.attrib and "IconSize" in node.attrib:
            tab.tab_icon_size = _int_attr(node, "IconSize", 32)

        tab.text_alignment = _int_attr(node, "TextAlignment", getattr(tab, "text_alignment", 0))
        tab.invert_text_color_on_sel = _int_attr(
            node,
            "InvertTextColorOnSel",
            getattr(tab, "invert_text_color_on_sel", 1),
        )


def _enrich_labels(theme, theme_node):
    nodes = _direct_children(theme_node, "Label")
    labels = list(getattr(theme, "labels", []) or [])
    for label, node in zip(labels, nodes):
        label.text_alignment = _int_attr(node, "TextAlignment", 0)


def enrich_theme(theme):
    """Add original GnoMenu fields to an already parsed Angujanu theme."""
    xml_path = getattr(theme, "xml_path", "") or ""
    if not xml_path or not os.path.isfile(xml_path):
        _enrich_dimensions(theme)
        return theme

    try:
        root = ET.fromstring(_read_xml_text(xml_path))
    except Exception as error:
        print(f"XFCEMenu: compat legacy no pudo releer XML: {error}")
        _enrich_dimensions(theme)
        return theme

    theme_node = _select_theme_node(root)
    if theme_node is None:
        _enrich_dimensions(theme)
        return theme

    # Keep the same variant as the base loader, and only enrich missing legacy
    # semantics. Full color-variant selection remains a separate feature.
    _enrich_dimensions(theme)
    _enrich_capabilities(theme, theme_node)
    _enrich_search(theme, theme_node)
    _enrich_images(theme, theme_node)
    _enrich_buttons(theme, theme_node)
    _enrich_tabs(theme, theme_node)
    _enrich_labels(theme, theme_node)

    print(
        "XFCEMenu: compat legacy enriquecida "
        f"(images={len(getattr(theme, 'images', []) or [])}, "
        f"capabilities={'sí' if getattr(theme, 'capabilities', None) else 'no'})"
    )
    return theme
