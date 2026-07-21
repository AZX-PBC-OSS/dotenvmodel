"""Tests for path resolution and require_exists options."""

from pathlib import Path

import pytest

from dotenvmodel import DotEnvConfig, Field
from dotenvmodel.exceptions import TypeCoercionError


class TestPathResolution:
    """Test resolve_path option."""

    def test_tilde_expanded_by_default(self) -> None:
        class Config(DotEnvConfig):
            path: Path = Field()

        config = Config.load_from_dict({"PATH": "~/logs"})
        assert config.path == Path.home() / "logs"

    def test_relative_resolved_by_default(self) -> None:
        class Config(DotEnvConfig):
            path: Path = Field()

        config = Config.load_from_dict({"PATH": "./output"})
        assert config.path == Path("./output").resolve()
        assert config.path.is_absolute()

    def test_disabled_keeps_raw(self) -> None:
        class Config(DotEnvConfig):
            path: Path = Field(resolve_path=False)

        config = Config.load_from_dict({"PATH": "~/logs"})
        assert config.path == Path("~/logs")

    def test_nonexistent_path_does_not_crash(self) -> None:
        class Config(DotEnvConfig):
            path: Path = Field()

        config = Config.load_from_dict({"PATH": "/nonexistent/path/that/does/not/exist"})
        assert isinstance(config.path, Path)

    def test_reload_resolves_path(self, monkeypatch) -> None:
        class Config(DotEnvConfig):
            log_dir: Path = Field(default=Path("/tmp"))

        monkeypatch.delenv("LOG_DIR", raising=False)
        config = Config.load()

        monkeypatch.setenv("LOG_DIR", "~/logs")
        config.reload()
        assert config.log_dir == Path.home() / "logs"


class TestRequireExists:
    """Test require_exists option."""

    def test_existing_path_passes(self, tmp_path: Path) -> None:
        class Config(DotEnvConfig):
            cert: Path = Field(require_exists=True)

        config = Config.load_from_dict({"CERT": str(tmp_path)})
        assert config.cert == tmp_path

    def test_nonexistent_path_raises(self) -> None:
        class Config(DotEnvConfig):
            cert: Path = Field(require_exists=True)

        with pytest.raises(TypeCoercionError) as exc_info:
            Config.load_from_dict({"CERT": "/nonexistent/path.pem"})
        assert "does not exist" in str(exc_info.value)

    def test_require_exists_with_resolve(self, tmp_path: Path) -> None:
        class Config(DotEnvConfig):
            cert: Path = Field(require_exists=True, resolve_path=True)

        # Create a symlink-like structure
        real_file = tmp_path / "cert.pem"
        real_file.touch()

        config = Config.load_from_dict({"CERT": str(real_file)})
        assert config.cert.exists()

    def test_require_exists_off_by_default(self) -> None:
        class Config(DotEnvConfig):
            cert: Path = Field()

        config = Config.load_from_dict({"CERT": "/nonexistent/path.pem"})
        assert isinstance(config.cert, Path)
