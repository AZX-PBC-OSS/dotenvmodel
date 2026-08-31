"""Isolation of mutable defaults between loads.

A literal ``Field(default=[...])`` (or a bare mutable class attr wrapped by the
metaclass) is deep-copied on every ``load()``, so instances never share default
objects. ``default_factory`` is invoked on every load and its result is handed
out as-is (never copied); a factory returning a shared object keeps that object
shared.
"""

import threading
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path
from uuid import UUID

import pytest

from dotenvmodel import DotEnvConfig, Field
from dotenvmodel.fields import FieldInfo, smart_deepcopy
from dotenvmodel.types import BaseDsn, HttpUrl, SecretStr

# A default_factory returning this documents factory-branch parity: factory
# results are handed out as-is (never copied).
_SHARED_HOSTS: list[str] = ["shared"]


class Color(Enum):
    RED = "red"


class TestLiteralMutableDefaults:
    """``Field(default=<mutable>)`` must be isolated per load."""

    def test_list_literal_default_not_shared_between_loads(self, monkeypatch, tmp_path) -> None:
        class Config(DotEnvConfig):
            hosts: list[str] = Field(default=["localhost"])

        monkeypatch.delenv("HOSTS", raising=False)

        a = Config.load(env="dev", env_dir=tmp_path)
        b = Config.load(env="dev", env_dir=tmp_path)
        assert a.hosts is not b.hosts

        a.hosts.append("corrupted")
        later = Config.load(env="dev", env_dir=tmp_path)
        assert later.hosts == ["localhost"]
        assert b.hosts == ["localhost"]

    def test_dict_literal_default_not_shared_between_loads(self) -> None:
        class Config(DotEnvConfig):
            limits: dict[str, str] = Field(default={"cpu": "4"})

        a = Config.load_from_dict({})
        b = Config.load_from_dict({})
        assert a.limits is not b.limits

        a.limits["cpu"] = "corrupted"
        assert Config.load_from_dict({}).limits == {"cpu": "4"}

    def test_bare_class_attr_list_default_not_shared(self) -> None:
        """Bare mutable class attrs are wrapped by the metaclass and isolated too."""

        class Config(DotEnvConfig):
            hosts: list[str] = ["localhost"]  # noqa: RUF012 — the bare-attr repro path

        a = Config.load_from_dict({})
        b = Config.load_from_dict({})
        assert a.hosts is not b.hosts

        a.hosts.append("corrupted")
        assert Config.load_from_dict({}).hosts == ["localhost"]

    def test_nested_mutables_in_default_deep_copied(self) -> None:
        class Config(DotEnvConfig):
            mapping: dict[str, list[str]] = Field(default={"hosts": ["a"]})

        a = Config.load_from_dict({})
        b = Config.load_from_dict({})
        assert a.mapping is not b.mapping
        assert a.mapping["hosts"] is not b.mapping["hosts"]

        a.mapping["hosts"].append("corrupted")
        assert Config.load_from_dict({}).mapping == {"hosts": ["a"]}


class TestImmutableDefaultsKeepIdentity:
    """Exact-type immutable defaults are handed out as-is: zero copy cost."""

    @pytest.mark.parametrize(
        "default",
        [
            None,
            True,
            False,
            42,
            3.14,
            1 + 2j,
            "text",
            b"bytes",
            range(3),
            datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
            date(2026, 1, 1),
            time(12, 0),
            timedelta(hours=1),
            Decimal("1.5"),
            UUID("12345678-1234-5678-1234-567812345678"),
            SecretStr("secret"),
            BaseDsn("postgres://user:pass@localhost:5432/db"),
        ],
    )
    def test_exact_type_immutable_default_returned_as_is(self, default: object) -> None:
        field_info = FieldInfo(default=default)
        assert field_info.get_default() is default

    @pytest.mark.parametrize(
        "default",
        [Path("/data"), HttpUrl("https://example.com")],
        ids=["posix-path", "http-url"],
    )
    def test_subclass_instance_default_copied_not_shared(self, default: object) -> None:
        """Subclasses (PosixPath, HttpUrl) can carry mutable state: deep-copied.

        Exact-type membership means only the declared types themselves take
        the zero-copy fast path; subclasses fall through to ``deepcopy`` and
        come back equal but independent.
        """
        field_info = FieldInfo(default=default)
        result = field_info.get_default()
        assert result == default
        assert result is not default

    def test_enum_member_default_returns_same_member(self) -> None:
        """Enum members are singletons: deepcopy hands back the identical member."""
        field_info = FieldInfo(default=Color.RED)
        assert field_info.get_default() is Color.RED


class TestDefaultFactoryParity:
    """Factory results are handed out as-is on every load, never copied."""

    def test_default_factory_result_fresh_per_load(self) -> None:
        class Config(DotEnvConfig):
            hosts: list[str] = Field(default_factory=list)

        a = Config.load_from_dict({})
        b = Config.load_from_dict({})
        assert a.hosts is not b.hosts

        a.hosts.append("corrupted")
        assert Config.load_from_dict({}).hosts == []

    def test_factory_returning_shared_module_list_not_copied(self) -> None:
        """Documents current behavior: factory results are returned as-is."""

        class Config(DotEnvConfig):
            hosts: list[str] = Field(default_factory=lambda: _SHARED_HOSTS)

        config = Config.load_from_dict({})
        assert config.hosts is _SHARED_HOSTS


class TestSmartDeepcopy:
    """Unit tests for the copy strategy behind literal-default isolation."""

    @pytest.mark.parametrize("value", [[], {}, set()])
    def test_empty_containers_copied_not_shared(self, value: object) -> None:
        result = smart_deepcopy(value)
        assert result == value
        assert result is not value

    def test_nonempty_container_deep_copied(self) -> None:
        original = {"hosts": ["a"], "ports": [1, 2]}
        result = smart_deepcopy(original)
        assert result == original
        assert result is not original
        assert result["hosts"] is not original["hosts"]
        assert result["ports"] is not original["ports"]

    def test_custom_object_deep_copied(self) -> None:
        class Widget:
            def __init__(self) -> None:
                self.parts: list[str] = []

        widget = Widget()
        widget.parts.append("a")
        result = smart_deepcopy(widget)
        assert result is not widget
        assert result.parts is not widget.parts
        assert result.parts == ["a"]

    def test_tuple_returns_equal_value(self) -> None:
        """Tuples are not on the zero-cost list; deepcopy still yields an equal value."""

        value = ("a", "b")
        assert smart_deepcopy(value) == value

    def test_str_subclass_with_mutable_state_isolated(self) -> None:
        """A str subclass carrying mutable state is isolated per call.

        ``isinstance`` checks would hand the SAME object to every load,
        sharing the mutable attribute — the exact bug class this module
        guards against. Exact-type membership routes subclasses to
        ``deepcopy`` instead.
        """

        class TaggedStr(str):
            metadata: list[str]

        original = TaggedStr("label")
        original.metadata = ["shared-state"]

        first = smart_deepcopy(original)
        second = smart_deepcopy(original)

        assert first is not original
        assert first.metadata is not original.metadata
        first.metadata.append("corrupted")
        assert second.metadata == ["shared-state"]
        assert original.metadata == ["shared-state"]

    def test_empty_list_subclass_keeps_its_type(self) -> None:
        """An empty list subclass is deep-copied, preserving its type.

        ``list.copy()`` would return a plain ``list``; ``deepcopy`` keeps
        the subclass.
        """

        class MyList(list[int]):
            pass

        value = MyList()
        result = smart_deepcopy(value)
        assert result == value
        assert result is not value
        assert type(result) is MyList

    def test_raising_bool_collection_does_not_crash(self) -> None:
        """A collection subclass whose ``__bool__`` raises must not crash.

        Truthiness tests like ``not value`` would invoke ``__bool__``;
        exact-type membership never evaluates truthiness.
        """

        class WeirdBoolList(list[int]):
            def __bool__(self) -> bool:
                raise ValueError("truthiness is undefined")

        result = smart_deepcopy(WeirdBoolList())
        assert isinstance(result, WeirdBoolList)


class TestDeepcopyableDefaultContract:
    """Literal defaults must be deep-copyable; failure is loud, not silent sharing."""

    def test_undeepcopyable_lock_default_raises_type_error_on_load(self) -> None:
        class Config(DotEnvConfig):
            name: str = Field(default="app")
            lock: object = Field(default=threading.Lock())

        with pytest.raises(TypeError):
            Config.load_from_dict({})
