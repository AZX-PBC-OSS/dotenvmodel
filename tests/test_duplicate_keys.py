"""Tests for duplicate-key detection in the .env cascade.

A key defined more than once is almost always an editing mistake; the
merge keeps last-wins (python-dotenv's own semantics, unchanged) but the
flip is now logged loudly - within a file and across the cascade.
"""

from pathlib import Path

from dotenvmodel.loading import read_env_files


class TestDuplicateKeyWarnings:
    def test_within_file_duplicate_warns_and_last_wins(self, tmp_path: Path, caplog) -> None:
        env_dir = tmp_path
        (env_dir / ".env").write_text("A=false\nB=keep\nA=true\n")

        with caplog.at_level("WARNING", logger="dotenvmodel"):
            layer = read_env_files(env="dev", env_dir=env_dir)

        # Semantics unchanged: the later occurrence wins.
        assert layer.values["A"] == "true"
        assert layer.values["B"] == "keep"
        assert any(
            "Duplicate key 'A'" in r.message and str(env_dir / ".env") in r.message
            for r in caplog.records
        )

    def test_clean_file_never_warns(self, tmp_path: Path, caplog) -> None:
        env_dir = tmp_path
        (env_dir / ".env").write_text("A=1\nB=2\n")

        with caplog.at_level("WARNING", logger="dotenvmodel"):
            layer = read_env_files(env="dev", env_dir=env_dir)

        assert layer.values["A"] == "1"
        assert not any("Duplicate key" in r.message for r in caplog.records)

    def test_multiline_quoted_value_does_not_false_positive(self, tmp_path: Path, caplog) -> None:
        env_dir = tmp_path
        # A quoted multi-line value CONTAINING a `KEY=`-shaped line must not
        # read as a duplicate (the tokenizer understands the quoting).
        (env_dir / ".env").write_text('PROMPT="line one\nKEY=not a key\nline two"\nA=1\nA=1\n')

        with caplog.at_level("WARNING", logger="dotenvmodel"):
            layer = read_env_files(env="dev", env_dir=env_dir)

        assert layer.values["A"] == "1"
        assert layer.values["PROMPT"] == "line one\nKEY=not a key\nline two"
        duplicates = [r for r in caplog.records if "Duplicate key" in r.message]
        assert len(duplicates) == 1
        assert "Duplicate key 'A'" in duplicates[0].message
        assert "PROMPT" not in duplicates[0].message

    def test_cross_cascade_redefinition_warns_naming_both_values(
        self, tmp_path: Path, caplog
    ) -> None:
        env_dir = tmp_path
        (env_dir / ".env").write_text("SHARED=base\nONLY_BASE=1\n")
        (env_dir / ".env.dev").write_text("SHARED=dev-specific\n")

        with caplog.at_level("WARNING", logger="dotenvmodel"):
            layer = read_env_files(env="dev", env_dir=env_dir)

        # The cascade keeps the later file's value.
        assert layer.values["SHARED"] == "dev-specific"
        assert layer.values["ONLY_BASE"] == "1"
        assert any(
            "redefined" in r.message and "'base'" in r.message and "'dev-specific'" in r.message
            for r in caplog.records
        )

    def test_three_occurrences_warn_once_per_key(self, tmp_path: Path, caplog) -> None:
        env_dir = tmp_path
        (env_dir / ".env").write_text("A=1\nA=2\nA=3\n")

        with caplog.at_level("WARNING", logger="dotenvmodel"):
            layer = read_env_files(env="dev", env_dir=env_dir)

        assert layer.values["A"] == "3"
        assert len([r for r in caplog.records if "Duplicate key 'A'" in r.message]) == 1
