"""Output renderers for describe: table, markdown, json, html, dotenv."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import TYPE_CHECKING

from dotenvmodel.describe.formatters import (
    MAX_WIDTHS,
    FieldDescription,
)

if TYPE_CHECKING:
    pass


def build_json_data(class_name: str, prefix: str, fields: list[FieldDescription]) -> dict:
    """Build JSON data structure for a config class."""
    return {
        "class_name": class_name,
        "env_prefix": prefix,
        "fields": [asdict(f) for f in fields],
    }


def _sanitize_for_table(value: str) -> str:
    """Replace newlines/carriage returns to prevent table formatting breaks."""
    return value.replace("\n", " ").replace("\r", "")


def _truncate(value: str, max_width: int) -> str:
    """Truncate a string to max_width with ellipsis."""
    if len(value) > max_width:
        return value[: max_width - 3] + "..."
    return value


def render_table(
    class_name: str,
    prefix: str,
    fields: list[FieldDescription],
    line_ending: str,
) -> str:
    """Render fields as ASCII table with dynamic column widths."""
    if not fields:
        return f"{class_name}{line_ending}{'=' * len(class_name)}{line_ending}{line_ending}No fields defined.{line_ending}"

    headers = ["ENV Variable", "Type", "Required", "Default", "Description", "Constraints"]

    widths = [len(h) for h in headers]
    for f in fields:
        widths[0] = max(widths[0], len(f.env_var))
        widths[1] = max(widths[1], len(f.type_name))
        widths[2] = max(widths[2], 3)
        widths[3] = max(widths[3], len(f.default))
        widths[4] = max(widths[4], len(f.description))
        widths[5] = max(widths[5], len(f.constraints))

    for i, max_width in MAX_WIDTHS.items():
        if i < len(widths):
            widths[i] = min(widths[i], max_width)

    lines: list[str] = []

    title = class_name
    if prefix:
        title += f" (prefix: {prefix})"
    lines.append(title)
    lines.append("=" * len(title))
    lines.append("")

    sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"

    lines.append(sep)
    header_row = "|"
    for i, h in enumerate(headers):
        header_row += f" {h:<{widths[i]}} |"
    lines.append(header_row)
    lines.append(sep)

    for f in fields:
        required_str = "Yes" if f.required else "No"

        env_var = _truncate(_sanitize_for_table(f.env_var), widths[0])
        type_name = _truncate(_sanitize_for_table(f.type_name), widths[1])
        default = _truncate(_sanitize_for_table(f.default), widths[3])
        description = _truncate(_sanitize_for_table(f.description), widths[4])
        constraints = _truncate(_sanitize_for_table(f.constraints), widths[5])

        row = "|"
        row += f" {env_var:<{widths[0]}} |"
        row += f" {type_name:<{widths[1]}} |"
        row += f" {required_str:<{widths[2]}} |"
        row += f" {default:<{widths[3]}} |"
        row += f" {description:<{widths[4]}} |"
        row += f" {constraints:<{widths[5]}} |"
        lines.append(row)

    lines.append(sep)

    return line_ending.join(lines)


def escape_markdown(text: str) -> str:
    """Escape markdown special characters."""
    for char in ["\\", "`", "*", "_", "{", "}", "[", "]", "(", ")", "#", "+", "-", ".", "!", "|"]:
        text = text.replace(char, "\\" + char)
    return text


def render_markdown(
    class_name: str,
    prefix: str,
    fields: list[FieldDescription],
    line_ending: str,
) -> str:
    """Render fields as Markdown table."""
    if not fields:
        return f"## {class_name}{line_ending}{line_ending}No fields defined.{line_ending}"

    lines: list[str] = []

    title = class_name
    if prefix:
        title += f" (prefix: `{escape_markdown(prefix)}`)"
    lines.append(f"## {title}")
    lines.append("")

    lines.append("| ENV Variable | Type | Required | Default | Description | Constraints |")
    lines.append("|--------------|------|----------|---------|-------------|-------------|")

    for f in fields:
        required_str = "Yes" if f.required else "No"

        env_var = escape_markdown(_sanitize_for_table(f.env_var))
        type_name = f"`{escape_markdown(_sanitize_for_table(f.type_name))}`"
        default = (
            f"`{escape_markdown(_sanitize_for_table(f.default))}`" if f.default != "-" else "-"
        )
        description = escape_markdown(_sanitize_for_table(f.description))
        constraints = (
            f"`{escape_markdown(_sanitize_for_table(f.constraints))}`"
            if f.constraints != "-"
            else "-"
        )

        lines.append(
            f"| {env_var} | {type_name} | {required_str} | {default} | {description} | {constraints} |"
        )

    return line_ending.join(lines)


def render_json(
    class_name: str,
    prefix: str,
    fields: list[FieldDescription],
    line_ending: str,
) -> str:
    """Render fields as JSON."""
    data = build_json_data(class_name, prefix, fields)
    result = json.dumps(data, indent=2)
    if line_ending != "\n":
        result = result.replace("\n", line_ending)
    return result


def render_dotenv(
    class_name: str,
    prefix: str,
    fields: list[FieldDescription],
    line_ending: str,
    include_descriptions: bool = True,
    include_examples: bool = True,
) -> str:
    """Render fields as a .env.example file."""
    lines: list[str] = []

    lines.append(f"# Configuration for {class_name}")
    if prefix:
        lines.append(f"# All variables prefixed with: {prefix}")
    lines.append("")

    for field in fields:
        if include_descriptions and field.description and field.description != "-":
            lines.append(f"# {field.description}")

        type_info = f"# Type: {field.type_name}"
        if field.constraints and field.constraints != "-":
            type_info += f" | Constraints: {field.constraints}"
        lines.append(type_info)

        if include_examples:
            if field.default and field.default not in ("-", "None", "<secret>"):
                lines.append(f"# Example: {field.env_var}={field.default}")
            elif field.type_name.startswith("list["):
                lines.append(f"# Example: {field.env_var}=value1,value2,value3")
            elif field.type_name == "int":
                lines.append(f"# Example: {field.env_var}=8000")
            elif field.type_name == "bool":
                lines.append(f"# Example: {field.env_var}=true")
            elif field.type_name == "str":
                lines.append(f"# Example: {field.env_var}=your_value_here")

        if field.required:
            lines.append(f"{field.env_var}=")
        else:
            if field.default == "<secret>":
                lines.append(f"# {field.env_var}=your_secret_here")
            elif field.default and field.default != "-":
                lines.append(f"# {field.env_var}={field.default}")
            else:
                lines.append(f"# {field.env_var}=")

        lines.append("")

    return line_ending.join(lines)


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_html(
    class_name: str,
    prefix: str,
    fields: list[FieldDescription],
    line_ending: str,
) -> str:
    """Render fields as an HTML table with styling."""
    lines: list[str] = []

    lines.append("<!DOCTYPE html>")
    lines.append("<html>")
    lines.append("<head>")
    lines.append(f"<title>{class_name} Configuration</title>")
    lines.append("<style>")
    lines.append(
        "  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; margin: 40px; }"
    )
    lines.append("  h1 { color: #333; }")
    lines.append("  .subtitle { color: #666; margin-top: -10px; }")
    lines.append("  table { border-collapse: collapse; width: 100%; margin-top: 20px; }")
    lines.append(
        "  th { background: #f6f8fa; border: 1px solid #d0d7de; padding: 12px; text-align: left; font-weight: 600; }"
    )
    lines.append("  td { border: 1px solid #d0d7de; padding: 12px; }")
    lines.append("  tr:nth-child(even) { background: #f6f8fa; }")
    lines.append("  .required-yes { color: #cf222e; font-weight: 600; }")
    lines.append("  .required-no { color: #1a7f37; }")
    lines.append(
        "  .type { font-family: 'Monaco', 'Courier New', monospace; background: #f6f8fa; padding: 2px 6px; border-radius: 3px; }"
    )
    lines.append("  .default { font-family: 'Monaco', 'Courier New', monospace; }")
    lines.append("  .secret { color: #cf222e; font-style: italic; }")
    lines.append("  .constraints { font-size: 0.9em; color: #666; }")
    lines.append("</style>")
    lines.append("</head>")
    lines.append("<body>")

    title = f"{class_name}"
    if prefix:
        title += f" <span class='subtitle'>(prefix: <code>{prefix}</code>)</span>"
    lines.append(f"<h1>{title}</h1>")

    if not fields:
        lines.append("<p>No fields defined.</p>")
    else:
        lines.append("<table>")
        lines.append("  <thead>")
        lines.append("    <tr>")
        for header in ["ENV Variable", "Type", "Required", "Default", "Description", "Constraints"]:
            lines.append(f"      <th>{header}</th>")
        lines.append("    </tr>")
        lines.append("  </thead>")
        lines.append("  <tbody>")

        for field in fields:
            env_var = _escape_html(field.env_var)
            type_name = _escape_html(field.type_name)
            default = _escape_html(field.default)
            description = _escape_html(field.description)
            constraints = _escape_html(field.constraints)

            required_class = "required-yes" if field.required else "required-no"
            required_text = "Yes" if field.required else "No"

            default_class = "default"
            if default == "&lt;secret&gt;":
                default_class += " secret"

            lines.append("    <tr>")
            lines.append(f"      <td><strong>{env_var}</strong></td>")
            lines.append(f"      <td><span class='type'>{type_name}</span></td>")
            lines.append(f"      <td><span class='{required_class}'>{required_text}</span></td>")
            lines.append(f"      <td><span class='{default_class}'>{default}</span></td>")
            lines.append(f"      <td>{description}</td>")
            lines.append(f"      <td><span class='constraints'>{constraints}</span></td>")
            lines.append("    </tr>")

        lines.append("  </tbody>")
        lines.append("</table>")

    lines.append("</body>")
    lines.append("</html>")

    return line_ending.join(lines)
