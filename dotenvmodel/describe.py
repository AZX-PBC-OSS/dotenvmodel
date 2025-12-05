"""Configuration description and documentation utilities."""

from __future__ import annotations

import json
import types
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Literal, Union, get_args, get_origin

if TYPE_CHECKING:
    from dotenvmodel.config import DotEnvConfig

from dotenvmodel.fields import _MISSING, FieldInfo
from dotenvmodel.loading import get_env_var_name

OutputFormat = Literal["table", "markdown", "json"]


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
        if truncate and len(pattern) > 20:
            pattern = pattern[:17] + "..."
        constraints.append(f"regex={pattern}")

    # General constraints
    if field_info.choices is not None:
        choices_str = ", ".join(str(c) for c in field_info.choices)
        if truncate and len(choices_str) > 25:
            choices_str = choices_str[:22] + "..."
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
    type_name = getattr(field_type, "__name__", str(field_type))
    if "Secret" in type_name:
        return "<secret>"

    if isinstance(default, str):
        if truncate and len(default) > 20:
            return f'"{default[:17]}..."'
        return f'"{default}"'

    if isinstance(default, bool):
        return str(default)

    if isinstance(default, (int, float)):
        return str(default)

    # For complex defaults, use repr but truncate
    repr_str = repr(default)
    if truncate and len(repr_str) > 25:
        return repr_str[:22] + "..."
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

    for field_name, (field_type, field_info) in config_cls._fields.items():
        env_var = get_env_var_name(field_name, field_info.alias, prefix)
        type_name = format_type_name(field_type)
        default_str = format_default(field_info, field_type, truncate=truncate)
        constraints_str = format_constraints(field_info, truncate=truncate)
        description = field_info.description or "-"

        if truncate and len(description) > 35:
            description = description[:32] + "..."

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


def render_table(
    class_name: str,
    prefix: str,
    fields: list[FieldDescription],
) -> str:
    """Render fields as ASCII table with dynamic column widths."""
    if not fields:
        return f"{class_name}\n{'=' * len(class_name)}\n\nNo fields defined.\n"

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
        row = "|"
        row += f" {f.env_var:<{widths[0]}} |"
        row += f" {f.type_name:<{widths[1]}} |"
        row += f" {required_str:<{widths[2]}} |"
        row += f" {f.default:<{widths[3]}} |"
        row += f" {f.description:<{widths[4]}} |"
        row += f" {f.constraints:<{widths[5]}} |"
        lines.append(row)

    lines.append(sep)

    return "\n".join(lines)


def render_markdown(
    class_name: str,
    prefix: str,
    fields: list[FieldDescription],
) -> str:
    """Render fields as Markdown table."""
    if not fields:
        return f"## {class_name}\n\nNo fields defined.\n"

    lines: list[str] = []

    # Title
    title = class_name
    if prefix:
        title += f" (prefix: `{prefix}`)"
    lines.append(f"## {title}")
    lines.append("")

    # Header
    lines.append("| ENV Variable | Type | Required | Default | Description | Constraints |")
    lines.append("|--------------|------|----------|---------|-------------|-------------|")

    # Rows
    for f in fields:
        required_str = "Yes" if f.required else "No"
        # Escape pipe characters in values
        env_var = f.env_var.replace("|", "\\|")
        type_name = f"`{f.type_name}`"
        default = f"`{f.default}`" if f.default != "-" else "-"
        description = f.description.replace("|", "\\|")
        constraints = f"`{f.constraints}`" if f.constraints != "-" else "-"

        lines.append(
            f"| {env_var} | {type_name} | {required_str} | {default} | {description} | {constraints} |"
        )

    return "\n".join(lines)


def render_json(
    class_name: str,
    prefix: str,
    fields: list[FieldDescription],
) -> str:
    """Render fields as JSON."""
    data = {
        "class_name": class_name,
        "env_prefix": prefix,
        "fields": [asdict(f) for f in fields],
    }
    return json.dumps(data, indent=2)


def describe_single(
    config_cls: type[DotEnvConfig],
    format: OutputFormat = "table",
) -> str:
    """
    Generate documentation for a single config class.

    Args:
        config_cls: The DotEnvConfig subclass to describe
        format: Output format - "table", "markdown", or "json"

    Returns:
        Formatted string describing the configuration
    """
    # For JSON, don't truncate values
    truncate = format != "json"
    class_name, prefix, fields = describe_class(config_cls, truncate=truncate)

    if format == "table":
        return render_table(class_name, prefix, fields)
    elif format == "markdown":
        return render_markdown(class_name, prefix, fields)
    elif format == "json":
        return render_json(class_name, prefix, fields)
    else:
        raise ValueError(f"Unknown format: {format}")


def describe_configs(
    config_classes: list[type[DotEnvConfig]],
    format: OutputFormat = "table",
) -> str:
    """
    Generate documentation for multiple config classes.

    All classes are merged into a single output, with each class
    shown as a separate section.

    Args:
        config_classes: List of DotEnvConfig subclasses to describe
        format: Output format - "table", "markdown", or "json"

    Returns:
        Formatted string describing all configurations
    """
    if not config_classes:
        return "No configuration classes provided."

    if format == "json":
        # For JSON, return an array of class descriptions
        results = []
        for cls in config_classes:
            class_name, prefix, fields = describe_class(cls, truncate=False)
            results.append(
                {
                    "class_name": class_name,
                    "env_prefix": prefix,
                    "fields": [asdict(f) for f in fields],
                }
            )
        return json.dumps(results, indent=2)

    # For table and markdown, concatenate sections
    sections = []
    for cls in config_classes:
        sections.append(describe_single(cls, format=format))

    separator = "\n\n" if format == "table" else "\n\n---\n\n"
    return separator.join(sections)
