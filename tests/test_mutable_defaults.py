"""Isolation of mutable defaults between loads (issue #58).

``FieldInfo.get_default()`` used to return the same literal object for
``Field(default=[...])`` (and for bare mutable class attrs wrapped by the
metaclass), so mutating one instance's value corrupted every other instance
and all future ``load()`` calls. Literal defaults are now deep-copied per
load; ``default_factory`` results are already fresh per call and stay
uncopied.
"""

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
    """Immutable defaults are handed out as-is: zero copy cost (pydantic parity)."""

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
            Color.RED,
            datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
            date(2026, 1, 1),
            time(12, 0),
            timedelta(hours=1),
            Decimal("1.5"),
            UUID("12345678-1234-5678-1234-567812345678"),
            Path("/data"),
            SecretStr("secret"),
            BaseDsn("postgres://user:pass@localhost:5432/db"),
            HttpUrl("https://example.com"),
        ],
    )
    def test_immutable_default_returned_as_is(self, default: object) -> None:
        field_info = FieldInfo(default=default)
        assert field_info.get_default() is default


class TestDefaultFactoryParity:
    """Factory results are already fresh per call and are never copied."""

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
