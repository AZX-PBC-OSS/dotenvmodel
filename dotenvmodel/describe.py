"""Configuration description and documentation utilities."""

from __future__ import annotations

import collections.abc
import json
import os
import types
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Union, get_args, get_origin

if TYPE_CHECKING:
    from dotenvmodel.config import DotEnvConfig

from dotenvmodel.fields import _MISSING, FieldInfo
from dotenvmodel.loading import get_env_var_name
from dotenvmodel.types import SecretStr

OutputFormat = Literal["table", "markdown", "json", "html", "dotenv"]

# Maximum column widths to prevent unbounded table growth
MAX_WIDTHS = {
    0: 40,  # ENV Variable
    1: 30,  # Type
    2: 8,  # Required
    3: 25,  # Default
    4: 40,  # Description
    5: 40,  # Constraints
}

# Truncation thresholds for different value types
TRUNCATE_THRESHOLD_SHORT = 20  # For concise values (regex, strings)
TRUNCATE_THRESHOLD_MEDIUM = 25  # For lists and complex types
TRUNCATE_THRESHOLD_LONG = 35  # For descriptions

# Type parsing hint mapping
TYPE_PARSING_HINTS = {
    "list": "comma-separated values",
    "set": "comma-separated unique values",
    "tuple": "comma-separated values",
    "dict": "comma-separated key:value pairs",
    "timedelta": "duration format (e.g., 5s, 1m, 1h, 1d, 1w) or seconds as int",
    "UUID": "UUID string",
    "Decimal": "decimal number string",
    "Path": "file or directory path",
    "HttpUrl": "HTTP(S) URL (e.g., https://example.com)",
    "PostgresDsn": "PostgreSQL DSN (e.g., postgresql://user:pass@localhost:5432/db)",
    "RedisDsn": "Redis DSN (e.g., redis://localhost:6379/0)",
    "Json": "valid JSON string",
    "SecretStr": "sensitive string (won't be logged)",
    "datetime": "ISO 8601 datetime string",
}


@dataclass
class FieldDescription:
    """Structured representation of a field for describe output."""

    env_var: str
    field_name: str
    type_name: str
    required: bool
    default: str
    description: str
    constraints: str


def format_type_name(field_type: type) -> str:
    """
    Format a type annotation as a readable string.

    Examples:
        int -> "int"
        list[str] -> "list[str]"
        str | None -> "str | None"
        Optional[int] -> "int | None"
        SecretStr -> "SecretStr"
    """
    # Handle NoneType specially
    if field_type is type(None):
        return "None"

    origin = get_origin(field_type)

    # Handle Union types (including str | None syntax which creates UnionType)
    if origin is types.UnionType or origin is Union:
        args = get_args(field_type)
        formatted_args = [format_type_name(arg) for arg in args]
        # Prefer "T | None" format
        if type(None) in args:
            non_none = [a for a in formatted_args if a != "None"]
            if len(non_none) == 1:
                return f"{non_none[0]} | None"
        return " | ".join(formatted_args)

    # Handle Callable types specially for clean output
    if origin is collections.abc.Callable:
        args = get_args(field_type)
        if args and len(args) == 2:
            param_types, return_type = args
            if isinstance(param_types, (list, tuple)):
                params = ", ".join(format_type_name(p) for p in param_types)
            else:
                # Ellipsis case: Callable[..., ReturnType]
                params = "..."
            ret = format_type_name(return_type)
            return f"Callable[[{params}], {ret}]"
        return "Callable"

    # Handle generic types (list[str], dict[str, int], etc.)
    if origin is not None:
        args = get_args(field_type)
        origin_name = getattr(origin, "__name__", str(origin))
        if args:
            arg_names = ", ".join(format_type_name(a) for a in args)
            return f"{origin_name}[{arg_names}]"
        return origin_name

    # Handle special types and basic types
    if hasattr(field_type, "__name__"):
        return field_type.__name__

    # Fallback for edge cases
    return str(field_type)


def get_type_parsing_hint(field_type: type, field_info: FieldInfo | None = None) -> str:
    """
    Get parsing hint for a type to help developers understand how to format values.

    Args:
        field_type: The field's type annotation
        field_info: Optional field metadata for custom separator info

    Returns:
        Human-readable hint about how to format this type

    Examples:
        list[str] -> "comma-separated values (e.g., value1,value2,value3)"
        timedelta -> "duration format (e.g., 5s, 1m, 1h, 1d, 1w) or seconds as int"
    """
    origin = get_origin(field_type)

    # Check for custom separator if it's a collection type
    if field_info and field_info.separator != "," and origin in (list, set, tuple):
        sep = field_info.separator
        return f"{sep}-separated values (use {sep} as delimiter)"

    # Handle generic types
    if origin is not None:
        origin_name = getattr(origin, "__name__", str(origin))
        if origin_name in TYPE_PARSING_HINTS:
            hint = TYPE_PARSING_HINTS[origin_name]
            # For collections, add example
            if origin_name in ("list", "set", "tuple"):
                args = get_args(field_type)
                if args:
                    element_type = args[0]
                    element_name = getattr(element_type, "__name__", str(element_type))
                    if element_name == "int":
                        return f"{hint} (e.g., 1,2,3,4)"
                    elif element_name == "str":
                        return f"{hint} (e.g., value1,value2,value3)"
            return hint

    # Handle simple types
    simple_name = getattr(field_type, "__name__", None)
    if simple_name and simple_name in TYPE_PARSING_HINTS:
        return TYPE_PARSING_HINTS[simple_name]

    # Default - no special hint
    return ""


def generate_constraint_examples(field_type: type, field_info: FieldInfo) -> dict[str, list[str]]:
    """
    Generate valid and invalid examples for field constraints.

    Args:
        field_type: The field's type annotation
        field_info: The field metadata containing constraints

    Returns:
        Dictionary with 'valid' and 'invalid' example lists

    Examples:
        int with ge=1, le=100 -> {
            'valid': ['1', '50', '100'],
            'invalid': ['0 (too small)', '101 (too large)', 'abc (not a number)']
        }
    """
    valid = []
    invalid = []

    type_name = getattr(field_type, "__name__", str(field_type))
    origin = get_origin(field_type)
    if origin:
        type_name = getattr(origin, "__name__", str(origin))

    # Numeric constraints
    if (
        field_info.ge is not None
        or field_info.le is not None
        or field_info.gt is not None
        or field_info.lt is not None
    ) and type_name in ("int", "float"):
        # Determine bounds
        lower = field_info.ge if field_info.ge is not None else field_info.gt
        upper = field_info.le if field_info.le is not None else field_info.lt

        if lower is not None and upper is not None:
            mid = (lower + upper) // 2 if type_name == "int" else (lower + upper) / 2
            valid.extend([str(lower), str(mid), str(upper)])
            invalid.append(f"{lower - 1} (too small)")
            invalid.append(f"{upper + 1} (too large)")
        elif lower is not None:
            valid.extend([str(lower), str(lower + 10)])
            invalid.append(f"{lower - 1} (too small)")
        elif upper is not None:
            valid.extend([str(upper - 10), str(upper)])
            invalid.append(f"{upper + 1} (too large)")

        # Type error
        invalid.append(f"abc (not a {type_name})")

    # String length constraints
    if field_info.min_length is not None or field_info.max_length is not None:
        min_len = field_info.min_length or 0
        max_len = field_info.max_length or 100

        if field_info.min_length and field_info.max_length:
            valid.append(f"{'x' * min_len} ({min_len} chars)")
            mid_len = (min_len + max_len) // 2
            valid.append(f"{'x' * mid_len} ({mid_len} chars)")
            valid.append(f"{'x' * max_len} ({max_len} chars)")
            if min_len > 0:
                invalid.append(f"{'x' * (min_len - 1)} (too short)")
            invalid.append(f"{'x' * (max_len + 1)} (too long)")
        elif field_info.min_length:
            valid.append(f"{'x' * min_len} (minimum length)")
            valid.append(f"{'x' * (min_len + 5)}")
            if min_len > 0:
                invalid.append(f"{'x' * (min_len - 1)} (too short)")
        elif field_info.max_length:
            valid.append(f"{'x' * (max_len // 2)}")
            valid.append(f"{'x' * max_len} (maximum length)")
            invalid.append(f"{'x' * (max_len + 1)} (too long)")

    # Choices constraint
    if field_info.choices is not None:
        valid.extend([str(c) for c in field_info.choices[:3]])
        if len(field_info.choices) > 0:
            invalid.append("invalid_choice (not in allowed choices)")

    # Collection size constraints
    if field_info.min_items is not None or field_info.max_items is not None:
        min_items = field_info.min_items or 0
        max_items = field_info.max_items or 10

        if field_info.min_items and field_info.max_items:
            valid.append(f"{','.join(['item'] * min_items)} ({min_items} items)")
            valid.append(f"{','.join(['item'] * max_items)} ({max_items} items)")
            if min_items > 0:
                invalid.append(f"{','.join(['item'] * (min_items - 1))} (too few items)")
            invalid.append(f"{','.join(['item'] * (max_items + 1))} (too many items)")
        elif field_info.min_items:
            valid.append(f"{','.join(['item'] * min_items)} (minimum)")
            if min_items > 0:
                invalid.append(f"{','.join(['item'] * (min_items - 1))} (too few)")
        elif field_info.max_items:
            valid.append(f"{','.join(['item'] * max_items)} (maximum)")
            invalid.append(f"{','.join(['item'] * (max_items + 1))} (too many)")

    return {"valid": valid, "invalid": invalid}


def format_constraints(field_info: FieldInfo, truncate: bool = True) -> str:
    """
    Format field constraints as a readable string.

    Args:
        field_info: The field metadata
        truncate: Whether to truncate long values (for table display)

    Examples:
        ge=1, le=100 -> "ge=1, le=100"
        min_length=8 -> "min_length=8"
        choices=["a", "b"] -> "choices=[a, b]"
    """
    constraints: list[str] = []

    # Numeric constraints
    if field_info.ge is not None:
        constraints.append(f"ge={field_info.ge}")
    if field_info.le is not None:
        constraints.append(f"le={field_info.le}")
    if field_info.gt is not None:
        constraints.append(f"gt={field_info.gt}")
    if field_info.lt is not None:
        constraints.append(f"lt={field_info.lt}")

    # String constraints
    if field_info.min_length is not None:
        constraints.append(f"min_length={field_info.min_length}")
    if field_info.max_length is not None:
        constraints.append(f"max_length={field_info.max_length}")
    if field_info.regex is not None:
        pattern = field_info.regex
        if truncate and len(pattern) > TRUNCATE_THRESHOLD_SHORT:
            pattern = pattern[: TRUNCATE_THRESHOLD_SHORT - 3] + "..."
        constraints.append(f"regex={pattern}")

    # General constraints
    if field_info.choices is not None:
        choices_str = ", ".join(str(c) for c in field_info.choices)
        if truncate and len(choices_str) > TRUNCATE_THRESHOLD_MEDIUM:
            choices_str = choices_str[: TRUNCATE_THRESHOLD_MEDIUM - 3] + "..."
        constraints.append(f"choices=[{choices_str}]")

    # Collection constraints
    if field_info.min_items is not None:
        constraints.append(f"min_items={field_info.min_items}")
    if field_info.max_items is not None:
        constraints.append(f"max_items={field_info.max_items}")

    # UUID constraint
    if field_info.uuid_version is not None:
        constraints.append(f"uuid_version={field_info.uuid_version}")

    # Separator (only if non-default)
    if field_info.separator != ",":
        constraints.append(f"separator={field_info.separator!r}")

    return ", ".join(constraints) if constraints else "-"


def format_default(field_info: FieldInfo, field_type: type, truncate: bool = True) -> str:
    """
    Format default value for display.

    Args:
        field_info: The field metadata
        field_type: The field's type annotation
        truncate: Whether to truncate long values (for table display)

    Examples:
        _MISSING -> "-"
        None -> "None"
        "" -> '""'
        "value" -> '"value"'
        123 -> "123"
        default_factory=list -> "[]"
    """
    # Check if field is required (no default)
    if field_info.default is _MISSING and field_info.default_factory is None:
        return "-"

    # Handle default_factory
    if field_info.default_factory is not None:
        factory = field_info.default_factory
        if factory is list:
            return "[]"
        if factory is dict:
            return "{}"
        if factory is set:
            return "set()"
        # For custom factories, show the function name
        return f"<{getattr(factory, '__name__', 'factory')}()>"

    default = field_info.default

    if default is None:
        return "None"

    # Check if this is a SecretStr type and hide the value
    if isinstance(field_type, type) and issubclass(field_type, SecretStr):
        return "<secret>"

    if isinstance(default, str):
        if truncate and len(default) > TRUNCATE_THRESHOLD_SHORT:
            return f'"{default[: TRUNCATE_THRESHOLD_SHORT - 3]}..."'
        return f'"{default}"'

    if isinstance(default, bool):
        return str(default)

    if isinstance(default, (int, float)):
        return str(default)

    # For complex defaults, use repr but truncate
    repr_str = repr(default)
    if truncate and len(repr_str) > TRUNCATE_THRESHOLD_MEDIUM:
        return repr_str[: TRUNCATE_THRESHOLD_MEDIUM - 3] + "..."
    return repr_str


def describe_class(
    config_cls: type[DotEnvConfig],
    truncate: bool = True,
) -> tuple[str, str, list[FieldDescription]]:
    """
    Extract field descriptions from a config class.

    Args:
        config_cls: The DotEnvConfig subclass to describe
        truncate: Whether to truncate long values (for table display)

    Returns:
        Tuple of (class_name, env_prefix, list of FieldDescription)
    """
    class_name = config_cls.__name__
    prefix = getattr(config_cls, "env_prefix", "")
    fields: list[FieldDescription] = []

    for field_name, (field_type, field_info) in config_cls.get_fields().items():
        env_var = get_env_var_name(field_name, field_info.alias, prefix)
        type_name = format_type_name(field_type)
        default_str = format_default(field_info, field_type, truncate=truncate)
        constraints_str = format_constraints(field_info, truncate=truncate)
        description = field_info.description or "-"

        if truncate and len(description) > TRUNCATE_THRESHOLD_LONG:
            description = description[: TRUNCATE_THRESHOLD_LONG - 3] + "..."

        fields.append(
            FieldDescription(
                env_var=env_var,
                field_name=field_name,
                type_name=type_name,
                required=field_info.required,
                default=default_str,
                description=description,
                constraints=constraints_str,
            )
        )

    return class_name, prefix, fields


def build_json_data(class_name: str, prefix: str, fields: list[FieldDescription]) -> dict:
    """Build JSON data structure for a config class."""
    return {
        "class_name": class_name,
        "env_prefix": prefix,
        "fields": [asdict(f) for f in fields],
    }


def render_table(
    class_name: str,
    prefix: str,
    fields: list[FieldDescription],
    line_ending: str,
) -> str:
    """
    Render fields as ASCII table with dynamic column widths.

    Args:
        class_name: Name of the configuration class
        prefix: Environment variable prefix
        fields: List of field descriptions
        line_ending: Line ending to use for separating lines

    Returns:
        ASCII table formatted string
    """
    if not fields:
        return f"{class_name}{line_ending}{'=' * len(class_name)}{line_ending}{line_ending}No fields defined.{line_ending}"

    # Column headers
    headers = ["ENV Variable", "Type", "Required", "Default", "Description", "Constraints"]

    # Calculate column widths
    widths = [len(h) for h in headers]
    for f in fields:
        widths[0] = max(widths[0], len(f.env_var))
        widths[1] = max(widths[1], len(f.type_name))
        widths[2] = max(widths[2], 3)  # "Yes" or "No"
        widths[3] = max(widths[3], len(f.default))
        widths[4] = max(widths[4], len(f.description))
        widths[5] = max(widths[5], len(f.constraints))

    # Apply maximum width constraints
    for i, max_width in MAX_WIDTHS.items():
        if i < len(widths):
            widths[i] = min(widths[i], max_width)

    # Build table
    lines: list[str] = []

    # Title
    title = class_name
    if prefix:
        title += f" (prefix: {prefix})"
    lines.append(title)
    lines.append("=" * len(title))
    lines.append("")

    # Horizontal separator
    sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"

    # Header row
    lines.append(sep)
    header_row = "|"
    for i, h in enumerate(headers):
        header_row += f" {h:<{widths[i]}} |"
    lines.append(header_row)
    lines.append(sep)

    # Data rows
    for f in fields:
        required_str = "Yes" if f.required else "No"

        # Sanitize newlines and carriage returns to prevent table breaks
        env_var = f.env_var.replace("\n", " ").replace("\r", "")
        type_name = f.type_name.replace("\n", " ").replace("\r", "")
        default = f.default.replace("\n", " ").replace("\r", "")
        description = f.description.replace("\n", " ").replace("\r", "")
        constraints = f.constraints.replace("\n", " ").replace("\r", "")

        # Truncate values that exceed column width with ellipsis
        if len(env_var) > widths[0]:
            env_var = env_var[: widths[0] - 3] + "..."
        if len(type_name) > widths[1]:
            type_name = type_name[: widths[1] - 3] + "..."
        if len(default) > widths[3]:
            default = default[: widths[3] - 3] + "..."
        if len(description) > widths[4]:
            description = description[: widths[4] - 3] + "..."
        if len(constraints) > widths[5]:
            constraints = constraints[: widths[5] - 3] + "..."

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
    """
    Render fields as Markdown table.

    Args:
        class_name: Name of the configuration class
        prefix: Environment variable prefix
        fields: List of field descriptions
        line_ending: Line ending to use for separating lines

    Returns:
        Markdown formatted string
    """
    if not fields:
        return f"## {class_name}{line_ending}{line_ending}No fields defined.{line_ending}"

    lines: list[str] = []

    # Title
    title = class_name
    if prefix:
        title += f" (prefix: `{escape_markdown(prefix)}`)"
    lines.append(f"## {title}")
    lines.append("")

    # Header
    lines.append("| ENV Variable | Type | Required | Default | Description | Constraints |")
    lines.append("|--------------|------|----------|---------|-------------|-------------|")

    # Rows
    for f in fields:
        required_str = "Yes" if f.required else "No"

        # Sanitize newlines and carriage returns before escaping markdown
        env_var = escape_markdown(f.env_var.replace("\n", " ").replace("\r", ""))
        type_name = f"`{escape_markdown(f.type_name.replace('\n', ' ').replace('\r', ''))}`"
        default = (
            f"`{escape_markdown(f.default.replace('\n', ' ').replace('\r', ''))}`"
            if f.default != "-"
            else "-"
        )
        description = escape_markdown(f.description.replace("\n", " ").replace("\r", ""))
        constraints = (
            f"`{escape_markdown(f.constraints.replace('\n', ' ').replace('\r', ''))}`"
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
    """
    Render fields as JSON.

    Note: JSON spec requires internal structure to use \\n, but the result
    can be post-processed to use custom line endings if needed.
    """
    data = build_json_data(class_name, prefix, fields)
    result = json.dumps(data, indent=2)
    # If custom line ending is different from \n, replace all \n with custom line ending
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
    """
    Render fields as a .env.example file.

    Args:
        class_name: Name of the configuration class
        prefix: Environment variable prefix
        fields: List of field descriptions
        line_ending: Line ending to use for separating lines
        include_descriptions: Include description comments
        include_examples: Include constraint examples as comments

    Returns:
        .env.example file content
    """
    lines = []

    # Add header
    lines.append(f"# Configuration for {class_name}")
    if prefix:
        lines.append(f"# All variables prefixed with: {prefix}")
    lines.append("")

    for field in fields:
        # Add description as comment
        if include_descriptions and field.description and field.description != "-":
            lines.append(f"# {field.description}")

        # Add type and constraints info
        type_info = f"# Type: {field.type_name}"
        if field.constraints and field.constraints != "-":
            type_info += f" | Constraints: {field.constraints}"
        lines.append(type_info)

        # Add examples if requested
        if include_examples:
            # Check if we can generate examples from the field (we need the actual FieldInfo)
            # For now, we'll show valid values based on defaults or constraints
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

        # Add the actual variable line
        if field.required:
            # Required fields get no value (user must fill in)
            lines.append(f"{field.env_var}=")
        else:
            # Optional fields show their default or placeholder
            if field.default == "<secret>":
                lines.append(f"# {field.env_var}=your_secret_here")
            elif field.default and field.default != "-":
                lines.append(f"# {field.env_var}={field.default}")
            else:
                lines.append(f"# {field.env_var}=")

        lines.append("")  # Blank line between fields

    return line_ending.join(lines)


def render_html(
    class_name: str,
    prefix: str,
    fields: list[FieldDescription],
    line_ending: str,
) -> str:
    """
    Render fields as an HTML table.

    Args:
        class_name: Name of the configuration class
        prefix: Environment variable prefix
        fields: List of field descriptions
        line_ending: Line ending to use for separating lines

    Returns:
        HTML table with styling
    """
    lines = []

    # Add HTML header with embedded CSS
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

    # Add title
    title = f"{class_name}"
    if prefix:
        title += f" <span class='subtitle'>(prefix: <code>{prefix}</code>)</span>"
    lines.append(f"<h1>{title}</h1>")

    # Handle empty config
    if not fields:
        lines.append("<p>No fields defined.</p>")
    else:
        # Add table
        lines.append("<table>")
        lines.append("  <thead>")
        lines.append("    <tr>")
        lines.append("      <th>ENV Variable</th>")
        lines.append("      <th>Type</th>")
        lines.append("      <th>Required</th>")
        lines.append("      <th>Default</th>")
        lines.append("      <th>Description</th>")
        lines.append("      <th>Constraints</th>")
        lines.append("    </tr>")
        lines.append("  </thead>")
        lines.append("  <tbody>")

        for field in fields:
            # Escape HTML
            env_var = field.env_var.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            type_name = (
                field.type_name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            )
            default = field.default.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            description = (
                field.description.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            )
            constraints = (
                field.constraints.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            )

            # Required status with styling
            required_class = "required-yes" if field.required else "required-no"
            required_text = "Yes" if field.required else "No"

            # Secret styling
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


def describe_single(
    config_cls: type[DotEnvConfig],
    output_format: OutputFormat = "table",
    output: str | Path | None = None,
    line_ending: str | None = None,
) -> str:
    """
    Generate documentation for a single config class.

    Args:
        config_cls: The DotEnvConfig subclass to describe
        output_format: Output format - "table", "markdown", "json", "html", or "dotenv"
        output: Optional file path to save the output to
        line_ending: Line ending to use (e.g., "\\n", "\\r\\n", "\\r").
            If None, uses platform default (os.linesep)

    Returns:
        Formatted string describing the configuration

    Example:
        ```python
        # Generate markdown and save to file
        AppConfig.describe(output_format="markdown", output="docs/config.md")

        # Generate .env.example file
        AppConfig.describe(output_format="dotenv", output=".env.example")

        # Use Unix line endings regardless of platform
        AppConfig.describe(output_format="markdown", line_ending="\\n")

        # Use Windows line endings
        AppConfig.describe(output_format="markdown", line_ending="\\r\\n")
        ```
    """
    # Use platform default line ending if not specified
    line_ending = line_ending if line_ending is not None else os.linesep

    # For JSON and dotenv, don't truncate values
    truncate = output_format not in ("json", "dotenv", "html")
    class_name, prefix, fields = describe_class(config_cls, truncate=truncate)

    if output_format == "table":
        result = render_table(class_name, prefix, fields, line_ending)
    elif output_format == "markdown":
        result = render_markdown(class_name, prefix, fields, line_ending)
    elif output_format == "json":
        result = render_json(class_name, prefix, fields, line_ending)
    elif output_format == "html":
        result = render_html(class_name, prefix, fields, line_ending)
    elif output_format == "dotenv":
        result = render_dotenv(class_name, prefix, fields, line_ending)
    else:
        raise ValueError(f"Unknown output_format: {output_format}")

    # Save to file if output path provided
    if output:
        output_path = Path(output)
        output_path.write_text(result, encoding="utf-8")

    return result


def describe_configs(
    config_classes: list[type[DotEnvConfig]],
    output_format: OutputFormat = "table",
    output: str | Path | None = None,
    line_ending: str | None = None,
) -> str:
    """
    Generate documentation for multiple config classes.

    All classes are merged into a single output, with each class
    shown as a separate section.

    Args:
        config_classes: List of DotEnvConfig subclasses to describe
        output_format: Output format - "table", "markdown", "json", "html", or "dotenv"
        output: Optional file path to save the output to
        line_ending: Line ending to use (e.g., "\\n", "\\r\\n", "\\r").
            If None, uses platform default (os.linesep)

    Returns:
        Formatted string describing all configurations

    Example:
        ```python
        # Generate markdown documentation for all configs
        describe_configs([AppConfig, DatabaseConfig], output_format="markdown", output="docs/config.md")

        # Use Windows line endings
        describe_configs([AppConfig, DatabaseConfig], output_format="markdown", line_ending="\\r\\n")
        ```
    """
    if not config_classes:
        return "No configuration classes provided."

    # Use platform default line ending if not specified
    line_ending = line_ending if line_ending is not None else os.linesep

    if output_format == "json":
        # For JSON, return an array of class descriptions
        results = []
        for cls in config_classes:
            class_name, prefix, fields = describe_class(cls, truncate=False)
            results.append(build_json_data(class_name, prefix, fields))
        result = json.dumps(results, indent=2)
        # Replace newlines with custom line ending if needed
        if line_ending != "\n":
            result = result.replace("\n", line_ending)
    else:
        # For table, markdown, html, and dotenv, concatenate sections
        sections = []
        for cls in config_classes:
            sections.append(
                describe_single(cls, output_format=output_format, line_ending=line_ending)
            )

        if output_format == "table":
            separator = line_ending + line_ending
        elif output_format in ("markdown", "html"):
            separator = line_ending + line_ending + "---" + line_ending + line_ending
        else:  # dotenv
            separator = line_ending + line_ending
        result = separator.join(sections)

    # Save to file if output path provided
    if output:
        output_path = Path(output)
        output_path.write_text(result, encoding="utf-8")

    return result


def generate_env_example(
    config_cls: type[DotEnvConfig],
    output: str | Path | None = None,
    include_descriptions: bool = True,
    include_examples: bool = True,
) -> str:
    """
    Generate a .env.example file for onboarding new developers.

    This is a convenience function that calls describe_single with output_format="dotenv".

    Args:
        config_cls: The DotEnvConfig subclass to generate example for
        output: Optional file path to save the .env.example to
        include_descriptions: Include description comments
        include_examples: Include example values as comments

    Returns:
        .env.example file content

    Example:
        ```python
        # Generate .env.example file
        AppConfig.generate_env_example(output=".env.example")

        # Print to console
        print(AppConfig.generate_env_example())
        ```
    """
    return describe_single(config_cls, output_format="dotenv", output=output)
