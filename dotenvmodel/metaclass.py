"""Metaclass for DotEnvConfig field discovery."""

from __future__ import annotations

import sys
from typing import Any, get_args, get_origin, get_type_hints

from dotenvmodel.fields import _MISSING, FieldInfo, _RequiredSentinel


def _is_optional_type(field_type: type) -> bool:
    """Check if a type is Optional (Union with None)."""
    origin = get_origin(field_type)
    if origin is not None:
        args = get_args(field_type)
        return type(None) in args
    return False


def _get_annotations_from_namespace(namespace: dict[str, Any]) -> dict[str, Any]:
    """Extract annotations from a class namespace dict.

    On Python 3.14+ (PEP 649/749), annotations are lazily evaluated and
    __annotations__ is not in the namespace during metaclass __new__.
    Instead, an __annotate_func__ is present and must be called to get
    the actual annotation values.
    """
    if "__annotations__" in namespace:
        return namespace["__annotations__"]

    if sys.version_info >= (3, 14):
        import annotationlib

        annotate_func = annotationlib.get_annotate_from_class_namespace(namespace)
        if annotate_func is not None:
            try:
                return annotate_func(annotationlib.Format.VALUE)
            except Exception:
                pass

    return {}


def _resolve_type_hints(cls: type) -> dict[str, Any]:
    """Resolve string annotations to actual types.

    Uses get_type_hints which handles both PEP 563 (future import)
    and Python 3.14+ lazy annotations (PEP 649/749).
    """
    field_names = set(cls._fields.keys())  # type: ignore[attr-defined]
    if not field_names:
        return {}

    try:
        hints = get_type_hints(cls)
        return {k: v for k, v in hints.items() if k in field_names}
    except Exception:
        return {}


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

        # Eagerly validate a class-level strip_strings setting: a non-bool
        # value is rejected at class-definition time so it can never silently
        # produce char-set stripping (e.g. "true" -> strips t/r/u/e chars) or
        # be treated as truthy (e.g. 1). Only a value present in THIS class's
        # namespace is checked; inherited values were validated at their own
        # definition time.
        if "strip_strings" in namespace and not isinstance(namespace["strip_strings"], bool):
            raise TypeError(
                f"strip_strings must be a bool, got "
                f"{type(namespace['strip_strings']).__name__}: "
                f"{namespace['strip_strings']!r}"
            )

        hints = _get_annotations_from_namespace(namespace)

        for field_name, field_type in hints.items():
            if field_name.startswith("_"):
                continue
            # Class-level settings, not fields
            if field_name in ("env_prefix", "strip_strings"):
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
            # Set to None instead of removing so __annotate__ can still resolve
            # the name on Python 3.14+ (PEP 649). FieldInfo objects must not
            # remain as class attributes since they'd be shared across instances.
            if field_name in namespace:
                namespace[field_name] = None

        namespace["_fields"] = fields
        cls = super().__new__(mcs, name, bases, namespace)

        # Resolve string annotations (PEP 563 future import or Python 3.14+ lazy annotations)
        if any(isinstance(ft, str) for ft, _ in cls._fields.values()):  # type: ignore[attr-defined]
            resolved = _resolve_type_hints(cls)
            if resolved:
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

        return cls
