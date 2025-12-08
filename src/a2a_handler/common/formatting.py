"""Formatting utilities for Handler."""

import re
from typing import Any


def format_field_name(name: str) -> str:
    """Convert snake_case or camelCase to Title Case.

    Args:
        name: The field name to format.

    Returns:
        The formatted field name in Title Case.

    Examples:
        >>> format_field_name("snake_case")
        'Snake Case'
        >>> format_field_name("camelCase")
        'Camel Case'
        >>> format_field_name("already Title")
        'Already Title'
    """
    name = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
    name = name.replace("_", " ")
    return name.title()


def format_value(value: Any, indent: int = 0) -> str:
    """Recursively format a value for display, returning only truthy content.

    Handles None, empty strings, empty lists/dicts, bools, strings, numbers,
    lists (including Pydantic models), dicts, and objects with model_dump().

    Args:
        value: The value to format.
        indent: The current indentation level.

    Returns:
        A formatted string representation, or empty string for falsy values.
    """
    prefix = "  " * indent

    if value is None or value == "" or value == [] or value == {}:
        return ""

    if isinstance(value, bool):
        return "✓" if value else "✗"

    if isinstance(value, str):
        return value

    if isinstance(value, int | float):
        return str(value)

    if isinstance(value, list):
        lines: list[str] = []
        for item in value:
            if hasattr(item, "model_dump"):
                item_dict: dict[str, Any] = item.model_dump()
                name = item_dict.get("name") or item_dict.get("id") or "Item"
                desc = item_dict.get("description") or ""
                if desc:
                    desc_prefix = "  " * (indent + 1)
                    lines.append(f"{prefix}  • [cyan]{name}[/cyan]")
                    lines.append(f"{desc_prefix}  {desc}")
                else:
                    lines.append(f"{prefix}  • [cyan]{name}[/cyan]")
            elif isinstance(item, dict):
                item_d: dict[str, Any] = item
                name = item_d.get("name") or item_d.get("id") or "Item"
                desc = item_d.get("description") or ""
                if desc:
                    desc_prefix = "  " * (indent + 1)
                    lines.append(f"{prefix}  • [cyan]{name}[/cyan]")
                    lines.append(f"{desc_prefix}  {desc}")
                else:
                    lines.append(f"{prefix}  • [cyan]{name}[/cyan]")
            else:
                formatted = format_value(item, indent)
                if formatted:
                    lines.append(f"{prefix}  • {formatted}")
        return "\n" + "\n".join(lines) if lines else ""

    if hasattr(value, "model_dump"):
        value = value.model_dump()

    if isinstance(value, dict):
        dict_lines: list[str] = []
        for k, v in value.items():
            if isinstance(k, str) and k.startswith("_"):
                continue
            formatted = format_value(v, indent + 1)
            if formatted:
                field_name = format_field_name(str(k))
                if "\n" in formatted:
                    dict_lines.append(
                        f"{prefix}[bold]{field_name}:[/bold]\n{formatted}"
                    )
                else:
                    dict_lines.append(f"{prefix}[bold]{field_name}:[/bold] {formatted}")
        return "\n".join(dict_lines) if dict_lines else ""

    return str(value) if value else ""
