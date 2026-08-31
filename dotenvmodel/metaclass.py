"""Metaclass for DotEnvConfig field discovery."""

from __future__ import annotations

import copy
import sys
from typing import Any, cast, get_args, get_origin, get_type_hints

from dotenvmodel.fields import (
    _MISSING,
    _VALIDATOR_SPECS_ATTR,
    FieldInfo,
    _hook_bind,
    _RequiredSentinel,
    _ValidatorHook,
    _ValidatorSpec,
)


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


def _resolve_type_hints(cls: ConfigMeta) -> dict[str, Any]:
    """Resolve string annotations to actual types.

    Uses get_type_hints which handles both PEP 563 (future import)
    and Python 3.14+ lazy annotations (PEP 649/749).
    """
    field_names = set(cls._fields.keys())
    if not field_names:
        return {}

    try:
        hints = get_type_hints(cls)
        return {k: v for k, v in hints.items() if k in field_names}
    except Exception:
        return {}


# Attributes through which a wrapper object can hold the function a
# @field_validator marker was placed on. The supported forms expose the
# marker directly; these wrappers hide it where collection never looks.
_HIDDEN_MARKER_ATTRS = ("fget", "func", "__wrapped__")


def _reject_hidden_validator_marker(class_name: str, attr_name: str, value: Any) -> None:
    """Fail class definition when a namespace value hides a validator marker.

    Supported hook forms (plain function, staticmethod, classmethod) expose
    the ``@field_validator`` marker where collection looks for it. Wrapping
    the decorated function in a ``@property``, ``@cached_property``, or a
    similar descriptor hides the marker on ``fget``/``func``/``__wrapped__``
    — collection would silently wire nothing, letting a hook (e.g. one
    rejecting weak secrets) disappear without any error.

    Raises:
        TypeError: If a marker is reachable only through a wrapper.
    """
    for probe in _HIDDEN_MARKER_ATTRS:
        inner = getattr(value, probe, None)
        if inner is None:
            continue
        if getattr(inner, _VALIDATOR_SPECS_ATTR, None):
            raise TypeError(
                f"@field_validator hook {class_name}.{attr_name} is wrapped in "
                f"{type(value).__name__}, which hides it from the metaclass; "
                "attach @field_validator to a plain method, staticmethod, or "
                "classmethod instead (a module-level function assigned in "
                "the class body also works)"
            )


def _collect_validator_hooks(
    class_name: str,
    namespace: dict[str, Any],
) -> list[tuple[str, _ValidatorSpec, _ValidatorHook]]:
    """Find `@field_validator`-decorated callables in a class namespace.

    Returns one entry per (attribute, registration) pair in class-body
    definition order, so hooks attach in the order they were written.
    staticmethod and classmethod wrappers are unwrapped to the underlying
    function, where the decorator places its marker — whichever order the
    two decorators were applied in. A marker hidden inside another wrapper
    (a property, say) is rejected instead of silently wiring nothing.

    Args:
        class_name: Name of the class being created, for error messages
        namespace: The class-body namespace being turned into a class

    Returns:
        Collected (attribute name, spec, hook) entries, in definition order
    """
    collected: list[tuple[str, _ValidatorSpec, _ValidatorHook]] = []
    for attr_name, value in namespace.items():
        func: Any = value
        if isinstance(value, (staticmethod, classmethod)):
            func = value.__func__
        specs = getattr(func, _VALIDATOR_SPECS_ATTR, None)
        if not specs:
            _reject_hidden_validator_marker(class_name, attr_name, value)
            continue
        bind = _hook_bind(func)
        for spec in specs:
            collected.append((attr_name, spec, _ValidatorHook(attr_name, func, bind)))
    return collected


def _clone_field_info(info: FieldInfo) -> FieldInfo:
    """Copy a FieldInfo so hook wiring in a subclass never mutates the parent's.

    The shallow copy shares immutable metadata (defaults, compiled regex,
    the inline validator); the hook lists are replaced with fresh lists so
    editing the subclass's hooks cannot touch the parent class's entries.
    """
    clone = copy.copy(info)
    clone.before_validators = list(info.before_validators)
    clone.after_validators = list(info.after_validators)
    return clone


def _wire_validator_hooks(
    class_name: str,
    namespace: dict[str, Any],
    fields: dict[str, tuple[type, FieldInfo]],
    own_fields: set[str],
) -> None:
    """Attach `@field_validator` hooks from a class namespace onto their fields.

    A registration naming a field that does not exist (after inheritance and
    this class's own annotations are assembled) fails here, at class
    definition time. Inherited hooks survive unless the subclass defines any
    same-named attribute: decorated again, the new method's hook replaces
    the inherited one; undecorated, the hook is removed. FieldInfo objects
    shared with a base class are copied before mutation, so the parent's
    wiring is never affected.

    Args:
        class_name: Name of the class being created, for error messages
        namespace: The class-body namespace being turned into a class
        fields: The assembled field map (inherited plus this class's own)
        own_fields: Field names whose FieldInfo was created in this class
            body (safe to mutate in place; the rest are shared with a base)
    """
    collected = _collect_validator_hooks(class_name, namespace)

    for attr_name, spec, _hook in collected:
        if spec.field_name not in fields:
            known = ", ".join(fields) or "(none)"
            raise ValueError(
                f'@field_validator("{spec.field_name}") on {class_name}.{attr_name} '
                f"does not match any field; known fields: {known}"
            )

    inherited_hooks = any(
        info.before_validators or info.after_validators for _, info in fields.values()
    )
    if not collected and not inherited_hooks:
        return

    shadowed = set(namespace)
    for field_name, (field_type, field_info) in fields.items():
        kept_before = [h for h in field_info.before_validators if h.method_name not in shadowed]
        kept_after = [h for h in field_info.after_validators if h.method_name not in shadowed]
        new_before = [
            hook
            for _attr, spec, hook in collected
            if spec.field_name == field_name and spec.mode == "before"
        ]
        new_after = [
            hook
            for _attr, spec, hook in collected
            if spec.field_name == field_name and spec.mode == "after"
        ]
        if (
            not new_before
            and not new_after
            and len(kept_before) == len(field_info.before_validators)
            and len(kept_after) == len(field_info.after_validators)
        ):
            continue
        if field_name not in own_fields:
            field_info = _clone_field_info(field_info)
            fields[field_name] = (field_type, field_info)
        field_info.before_validators = kept_before + new_before
        field_info.after_validators = kept_after + new_after


class ConfigMeta(type):
    """Metaclass that discovers field definitions on DotEnvConfig subclasses.

    Collects type annotations, associates them with FieldInfo metadata,
    inherits fields from parent classes, handles Optional defaults, and
    resolves string annotations when PEP 563 is active.
    """

    # Installed per-class in __new__ (namespace["_fields"]); declared here so
    # classes using this metaclass expose it to type checkers.
    _fields: dict[str, tuple[type, FieldInfo]]

    def __new__(mcs, name: str, bases: tuple[type, ...], namespace: dict[str, Any]) -> type:
        fields: dict[str, tuple[type, FieldInfo]] = {}
        for base in bases:
            if hasattr(base, "_fields"):
                base_fields = cast("dict[str, tuple[type, FieldInfo]]", base._fields)
                fields.update(base_fields)

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
        own_fields: set[str] = set()

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

            # Decorator hooks are attached to the field NAME on the class, so
            # they survive a subclass redeclaring the field with a fresh
            # Field(...) (whose own parameters reset per redeclaration).
            prior = fields.get(field_name)
            if prior is not None:
                field_info.before_validators = list(prior[1].before_validators)
                field_info.after_validators = list(prior[1].after_validators)

            fields[field_name] = (field_type, field_info)
            own_fields.add(field_name)
            # Set to None instead of removing so __annotate__ can still resolve
            # the name on Python 3.14+ (PEP 649). FieldInfo objects must not
            # remain as class attributes since they'd be shared across instances.
            if field_name in namespace:
                namespace[field_name] = None

        # Attach @field_validator hooks from this class body. Runs after the
        # field map is assembled so a hook may target an inherited field;
        # unknown names fail here, at class definition time.
        _wire_validator_hooks(name, namespace, fields, own_fields)

        namespace["_fields"] = fields
        cls = super().__new__(mcs, name, bases, namespace)

        # Resolve string annotations (PEP 563 future import or Python 3.14+ lazy annotations)
        if any(isinstance(ft, str) for ft, _ in cls._fields.values()):
            resolved = _resolve_type_hints(cls)
            if resolved:
                new_fields: dict[str, tuple[type, FieldInfo]] = {}
                for fname, (ftype, finfo) in cls._fields.items():
                    rtype = resolved.get(fname, ftype)
                    if (
                        finfo.default is _MISSING
                        and finfo.default_factory is None
                        and _is_optional_type(rtype)
                    ):
                        finfo.default = None
                        finfo.required = False
                    new_fields[fname] = (rtype, finfo)
                cls._fields = new_fields

        return cls
