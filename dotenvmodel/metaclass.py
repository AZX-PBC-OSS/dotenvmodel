"""Metaclass for DotEnvConfig field discovery."""

from __future__ import annotations

from typing import Any, get_args, get_origin, get_type_hints

from dotenvmodel.fields import _MISSING, FieldInfo, _RequiredSentinel


def _is_optional_type(field_type: type) -> bool:
    """Check if a type is Optional (Union with None)."""
    origin = get_origin(field_type)
    if origin is not None:
        args = get_args(field_type)
        return type(None) in args
    return False


class ConfigMeta(type):
    """Metaclass that discovers field definitions on DotEnvConfig subclasses.

    Collects type annotations, associates them with FieldInfo metadata,
    inherits fields from parent classes, handles Optional defaults, and
    resolves string annotations when PEP 563 is active.
    """

    def __new__(mcs, name: str, bases: tuple[type, ...], namespace: dict[str, Any]) -> type:
        fields: dict[str, tuple[type, FieldInfo]] = {}
        for base in bases:
            if hasattr(base, "_fields"):
                fields.update(base._fields)  # type: ignore[arg-type]

        hints = namespace.get("__annotations__", {})

        for field_name, field_type in hints.items():
            if field_name.startswith("_"):
                continue
            if field_name == "env_prefix":
                continue

            field_value = namespace.get(field_name, _MISSING)

            if isinstance(field_value, FieldInfo):
                field_info = field_value
                if (
                    field_info.default is _MISSING
                    and field_info.default_factory is None
                    and _is_optional_type(field_type)
                ):
                    field_info.default = None
                    field_info.required = False
            elif isinstance(field_value, _RequiredSentinel):
                field_info = FieldInfo()
            elif field_value is _MISSING:
                if _is_optional_type(field_type):
                    field_info = FieldInfo(default=None)
                else:
                    field_info = FieldInfo()
            elif field_value is ...:
                field_info = FieldInfo()
            else:
                field_info = FieldInfo(default=field_value)

            fields[field_name] = (field_type, field_info)
            namespace.pop(field_name, None)

        namespace["_fields"] = fields
        cls = super().__new__(mcs, name, bases, namespace)

        if any(isinstance(ft, str) for ft, _ in cls._fields.values()):  # type: ignore[attr-defined]
            try:
                resolved = get_type_hints(cls)
                new_fields: dict[str, tuple[type, FieldInfo]] = {}
                for fname, (ftype, finfo) in cls._fields.items():  # type: ignore[attr-defined]
                    rtype = resolved.get(fname, ftype)
                    if (
                        finfo.default is _MISSING
                        and finfo.default_factory is None
                        and _is_optional_type(rtype)
                    ):
                        finfo.default = None
                        finfo.required = False
                    new_fields[fname] = (rtype, finfo)
                cls._fields = new_fields  # type: ignore[method-assign]
            except Exception:
                pass

        return cls
