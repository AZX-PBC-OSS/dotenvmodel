"""Configuration description and documentation utilities.

Public API:
    - describe_single: Generate docs for a single config class
    - describe_configs: Generate docs for multiple config classes
    - generate_env_example: Convenience wrapper for .env.example generation
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from dotenvmodel.describe.formatters import FieldDescription as FieldDescription
from dotenvmodel.describe.formatters import describe_class
from dotenvmodel.describe.renderers import (
    build_json_data,
    render_dotenv,
    render_html,
    render_json,
    render_markdown,
    render_table,
)

if TYPE_CHECKING:
    from dotenvmodel.config import DotEnvConfig

OutputFormat = Literal["table", "markdown", "json", "html", "dotenv"]


def describe_single(
    config_cls: type[DotEnvConfig],
    output_format: OutputFormat = "table",
    output: str | Path | None = None,
    line_ending: str | None = None,
) -> str:
    """Generate documentation for a single config class.

    Args:
        config_cls: The DotEnvConfig subclass to describe
        output_format: Output format - "table" (default), "markdown", "json", "html", or "dotenv"
        output: Optional file path to save the output to
        line_ending: Line ending to use. If None, uses platform default (os.linesep)

    Returns:
        Formatted string describing the configuration

    Raises:
        ValueError: If output_format is not recognized

    Example:
        ```python
        AppConfig.describe(output_format="markdown", output="docs/config.md")
        AppConfig.describe(output_format="dotenv", output=".env.example")
        ```
    """
    line_ending = line_ending if line_ending is not None else os.linesep

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

    if output:
        Path(output).write_text(result, encoding="utf-8")

    return result


def describe_configs(
    config_classes: list[type[DotEnvConfig]],
    output_format: OutputFormat = "table",
    output: str | Path | None = None,
    line_ending: str | None = None,
) -> str:
    """Generate documentation for multiple config classes.

    Args:
        config_classes: List of DotEnvConfig subclasses to describe
        output_format: Output format - "table", "markdown", "json", "html", or "dotenv"
        output: Optional file path to save the output to
        line_ending: Line ending to use. If None, uses platform default

    Returns:
        Formatted string describing all configurations

    Example:
        ```python
        describe_configs([AppConfig, DatabaseConfig], output_format="markdown",
                         output="docs/configuration.md")
        ```
    """
    if not config_classes:
        return "No configuration classes provided."

    line_ending = line_ending if line_ending is not None else os.linesep

    if output_format == "json":
        results = []
        for cls in config_classes:
            class_name, prefix, fields = describe_class(cls, truncate=False)
            results.append(build_json_data(class_name, prefix, fields))
        result = json.dumps(results, indent=2)
        if line_ending != "\n":
            result = result.replace("\n", line_ending)
    else:
        sections = [
            describe_single(cls, output_format=output_format, line_ending=line_ending)
            for cls in config_classes
        ]

        if output_format == "table":
            separator = line_ending + line_ending
        elif output_format in ("markdown", "html"):
            separator = line_ending + line_ending + "---" + line_ending + line_ending
        else:
            separator = line_ending + line_ending
        result = separator.join(sections)

    if output:
        Path(output).write_text(result, encoding="utf-8")

    return result


def generate_env_example(
    config_cls: type[DotEnvConfig],
    output: str | Path | None = None,
) -> str:
    """Generate a .env.example file for onboarding.

    Convenience wrapper around describe_single with output_format="dotenv".

    Args:
        config_cls: The DotEnvConfig subclass to generate example for
        output: Optional file path to save the .env.example to

    Returns:
        .env.example file content as a string

    Example:
        ```python
        AppConfig.generate_env_example(output=".env.example")
        ```
    """
    return describe_single(config_cls, output_format="dotenv", output=output)
