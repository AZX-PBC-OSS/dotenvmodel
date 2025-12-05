"""Prefix derivation utilities for dotenvmodel."""

import re


def camel_to_screaming_snake(name: str) -> str:
    """
    Convert CamelCase to SCREAMING_SNAKE_CASE, keeping acronyms intact.

    Examples:
        - Database -> DATABASE
        - DatabaseConfig -> DATABASE_CONFIG
        - DBConfig -> DB_CONFIG
        - HTTPServerConfig -> HTTP_SERVER_CONFIG
        - OAuth2Config -> OAUTH2_CONFIG

    Args:
        name: CamelCase string to convert

    Returns:
        SCREAMING_SNAKE_CASE string
    """
    if not name:
        return ""

    # Pattern explanation:
    # 1. (?<=[a-z0-9])(?=[A-Z]) - lowercase/digit followed by uppercase (e.g., "database|Config")
    # 2. (?<=[A-Z]{2})(?=[A-Z][a-z]) - 2+ uppercase followed by uppercase+lowercase (e.g., "HTTP|Server")
    # This keeps acronyms together: "HTTPServer" -> "HTTP_Server" -> "HTTP_SERVER"
    # The {2} requirement prevents splitting "OAuth" -> "O_Auth" (only 1 uppercase before A)

    # Insert underscore before:
    # - uppercase letter that follows a lowercase letter or digit
    # - uppercase letter that is followed by lowercase (end of acronym, requires 2+ uppercase before)
    result = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name)
    result = re.sub(r"(?<=[A-Z]{2})(?=[A-Z][a-z])", "_", result)

    return result.upper()


def derive_prefix_from_class_name(class_name: str) -> str:
    """
    Derive environment variable prefix from class name.

    Rules:
    1. Single-word class names (e.g., "Config", "Database") -> no prefix
    2. Multi-word class names -> use all words except the last as prefix
    3. CamelCase is converted to SCREAMING_SNAKE_CASE
    4. Acronyms stay together (DB, HTTP, etc.)

    Examples:
        - Config -> "" (no prefix)
        - Database -> "" (no prefix)
        - DatabaseConfig -> "DATABASE"
        - DBConfig -> "DB"
        - HTTPServerConfig -> "HTTP_SERVER"
        - MyAppSettings -> "MY_APP"

    Args:
        class_name: The class name to derive prefix from

    Returns:
        Prefix string (without trailing underscore), or empty string for no prefix
    """
    if not class_name:
        return ""

    # Convert to SCREAMING_SNAKE_CASE first
    screaming = camel_to_screaming_snake(class_name)

    # Split by underscore
    parts = screaming.split("_")

    # Single word -> no prefix
    if len(parts) == 1:
        return ""

    # Multiple words -> all but last
    return "_".join(parts[:-1])
