"""Tests for collection size validators (min_items, max_items)."""

import pytest

from dotenvmodel import ConstraintViolationError, DotEnvConfig, Field


class TestCollectionSizeValidators:
    """Test min_items and max_items validators."""

    def test_list_min_items_valid(self) -> None:
        """Test list with min_items constraint - valid."""

        class Config(DotEnvConfig):
            allowed_ips: list[str] = Field(min_items=1)

        config = Config.load_from_dict({"ALLOWED_IPS": "192.168.1.1,10.0.0.1"})
        assert len(config.allowed_ips) == 2

    def test_list_min_items_violation(self) -> None:
        """Test list with min_items constraint - violation."""

        class Config(DotEnvConfig):
            allowed_ips: list[str] = Field(min_items=1)

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"ALLOWED_IPS": ""})

        assert "at least 1 items" in str(exc_info.value)
        assert "got 0" in str(exc_info.value)

    def test_list_max_items_valid(self) -> None:
        """Test list with max_items constraint - valid."""

        class Config(DotEnvConfig):
            backup_servers: list[str] = Field(max_items=3)

        config = Config.load_from_dict({"BACKUP_SERVERS": "server1,server2,server3"})
        assert len(config.backup_servers) == 3

    def test_list_max_items_violation(self) -> None:
        """Test list with max_items constraint - violation."""

        class Config(DotEnvConfig):
            backup_servers: list[str] = Field(max_items=3)

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"BACKUP_SERVERS": "s1,s2,s3,s4,s5"})

        assert "at most 3 items" in str(exc_info.value)
        assert "got 5" in str(exc_info.value)

    def test_list_min_max_items_valid(self) -> None:
        """Test list with both min_items and max_items - valid."""

        class Config(DotEnvConfig):
            nodes: list[str] = Field(min_items=2, max_items=5)

        config = Config.load_from_dict({"NODES": "node1,node2,node3"})
        assert len(config.nodes) == 3

    def test_list_min_max_items_too_few(self) -> None:
        """Test list with both min_items and max_items - too few items."""

        class Config(DotEnvConfig):
            nodes: list[str] = Field(min_items=2, max_items=5)

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"NODES": "node1"})

        assert "at least 2 items" in str(exc_info.value)

    def test_list_min_max_items_too_many(self) -> None:
        """Test list with both min_items and max_items - too many items."""

        class Config(DotEnvConfig):
            nodes: list[str] = Field(min_items=2, max_items=5)

        with pytest.raises(ConstraintViolationError) as exc_info:
            Config.load_from_dict({"NODES": "n1,n2,n3,n4,n5,n6"})

        assert "at most 5 items" in str(exc_info.value)

    def test_set_min_items(self) -> None:
        """Test set with min_items constraint."""

        class Config(DotEnvConfig):
            roles: set[str] = Field(min_items=1)

        config = Config.load_from_dict({"ROLES": "admin,user"})
        assert len(config.roles) == 2

        with pytest.raises(ConstraintViolationError):
            Config.load_from_dict({"ROLES": ""})

    def test_set_max_items(self) -> None:
        """Test set with max_items constraint."""

        class Config(DotEnvConfig):
            permissions: set[str] = Field(max_items=3)

        config = Config.load_from_dict({"PERMISSIONS": "read,write,execute"})
        assert len(config.permissions) == 3

        with pytest.raises(ConstraintViolationError):
            Config.load_from_dict({"PERMISSIONS": "read,write,execute,delete,create"})

    def test_set_deduplication(self) -> None:
        """Test that set deduplicates items before size validation."""

        class Config(DotEnvConfig):
            tags: set[str] = Field(max_items=3)

        # Even though 5 items are provided, only 3 unique values
        config = Config.load_from_dict({"TAGS": "tag1,tag2,tag3,tag1,tag2"})
        assert len(config.tags) == 3  # Deduplicated

    def test_tuple_min_items(self) -> None:
        """Test tuple with min_items constraint."""

        class Config(DotEnvConfig):
            coordinates: tuple[str, ...] = Field(min_items=2)

        config = Config.load_from_dict({"COORDINATES": "x,y,z"})
        assert len(config.coordinates) == 3

        with pytest.raises(ConstraintViolationError):
            Config.load_from_dict({"COORDINATES": "x"})

    def test_dict_min_items(self) -> None:
        """Test dict with min_items constraint."""

        class Config(DotEnvConfig):
            headers: dict[str, str] = Field(min_items=1)

        config = Config.load_from_dict({"HEADERS": "Content-Type=application/json"})
        assert len(config.headers) == 1

        with pytest.raises(ConstraintViolationError):
            Config.load_from_dict({"HEADERS": ""})

    def test_dict_max_items(self) -> None:
        """Test dict with max_items constraint."""

        class Config(DotEnvConfig):
            labels: dict[str, str] = Field(max_items=2)

        config = Config.load_from_dict({"LABELS": "env=prod,region=us-west"})
        assert len(config.labels) == 2

        with pytest.raises(ConstraintViolationError):
            Config.load_from_dict({"LABELS": "a=1,b=2,c=3,d=4"})

    def test_list_integers_size_validation(self) -> None:
        """Test size validation works with typed lists."""

        class Config(DotEnvConfig):
            ports: list[int] = Field(min_items=1, max_items=5)

        config = Config.load_from_dict({"PORTS": "8000,8001,8002"})
        assert config.ports == [8000, 8001, 8002]

        with pytest.raises(ConstraintViolationError):
            Config.load_from_dict({"PORTS": ""})

    def test_no_size_constraints(self) -> None:
        """Test collections without size constraints."""

        class Config(DotEnvConfig):
            items: list[str] = Field(default_factory=list)

        # Should accept any size
        config = Config.load_from_dict({"ITEMS": ""})
        assert config.items == []

        config = Config.load_from_dict({"ITEMS": "a,b,c,d,e,f,g,h,i,j"})
        assert len(config.items) == 10

    def test_default_factory_with_size_constraints(self) -> None:
        """Test default_factory respects size constraints."""

        class Config(DotEnvConfig):
            # Default empty list violates min_items when no value provided
            items: list[str] = Field(default_factory=list, min_items=1)

        # Should fail validation when using default
        with pytest.raises(ConstraintViolationError):
            Config.load_from_dict({})

    def test_exact_size_match(self) -> None:
        """Test collection with exact size requirement."""

        class Config(DotEnvConfig):
            triplet: tuple[str, ...] = Field(min_items=3, max_items=3)

        config = Config.load_from_dict({"TRIPLET": "a,b,c"})
        assert len(config.triplet) == 3

        with pytest.raises(ConstraintViolationError):
            Config.load_from_dict({"TRIPLET": "a,b"})

        with pytest.raises(ConstraintViolationError):
            Config.load_from_dict({"TRIPLET": "a,b,c,d"})
