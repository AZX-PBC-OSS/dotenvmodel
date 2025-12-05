"""Advanced types example showcasing UUID, Decimal, datetime, SecretStr, URLs, and JSON."""

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from dotenvmodel import DotEnvConfig, Field
from dotenvmodel.types import HttpUrl, Json, PostgresDsn, RedisDsn, SecretStr


class AdvancedConfig(DotEnvConfig):
    """Configuration with advanced type support."""

    # URL and DSN types
    api_url: HttpUrl = Field()
    database_url: PostgresDsn = Field()
    redis_url: RedisDsn = Field()

    # UUID types
    tenant_id: UUID = Field()
    correlation_id: UUID | None = Field(default=None)

    # Decimal for precise numbers
    price: Decimal = Field()
    tax_rate: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))

    # Datetime types
    created_at: datetime = Field()
    expires_at: datetime | None = Field(default=None)

    # Timedelta for durations
    cache_ttl: timedelta = Field()
    timeout: timedelta = Field()

    # SecretStr for sensitive data
    api_key: SecretStr = Field(min_length=32)
    jwt_secret: SecretStr = Field()

    # JSON types
    feature_flags: Json[dict[str, bool]] = Field()
    allowed_roles: Json[list[str]] = Field()

    # Collection size validation
    backup_servers: list[str] = Field(min_items=1, max_items=5)


if __name__ == "__main__":
    # Example configuration
    config = AdvancedConfig.load_from_dict(
        {
            # URLs and DSNs
            "API_URL": "https://api.example.com/v1",
            "DATABASE_URL": "postgresql://user:pass@localhost:5432/myapp",
            "REDIS_URL": "redis://localhost:6379/0",
            # UUIDs
            "TENANT_ID": "550e8400-e29b-41d4-a716-446655440000",
            # Decimals
            "PRICE": "19.99",
            "TAX_RATE": "0.0825",
            # Datetimes
            "CREATED_AT": "2025-01-15T10:30:00",
            # Timedeltas
            "CACHE_TTL": "1h30m",  # 1 hour 30 minutes
            "TIMEOUT": "30s",  # 30 seconds
            # Secrets
            "API_KEY": "super-secret-key-at-least-32-chars-long",
            "JWT_SECRET": "another-secret-token",
            # JSON
            "FEATURE_FLAGS": '{"new_ui": true, "beta_api": false}',
            "ALLOWED_ROLES": '["admin", "user", "guest"]',
            # Collections
            "BACKUP_SERVERS": "backup1.example.com,backup2.example.com",
        }
    )

    print("Advanced configuration loaded successfully!\n")

    # URL types - work like strings but provide parsed components
    print(f"API URL: {config.api_url}")
    print(f"  - Scheme: {config.api_url.scheme}")
    print(f"  - Host: {config.api_url.host}")
    print(f"  - Path: {config.api_url.path}\n")

    print(f"Database URL: {config.database_url}")
    print(f"  - Host: {config.database_url.host}")
    print(f"  - Port: {config.database_url.port}")
    print(f"  - Database: {config.database_url.database}")
    print(f"  - Username: {config.database_url.username}\n")

    print(f"Redis URL: {config.redis_url}")
    print(f"  - Host: {config.redis_url.host}")
    print(f"  - Port: {config.redis_url.port}")
    print(f"  - Database: {config.redis_url.database}\n")

    # UUID types
    print(f"Tenant ID: {config.tenant_id}")
    print(f"  - Type: {type(config.tenant_id).__name__}\n")

    # Decimal for precise arithmetic
    print(f"Price: ${config.price}")
    print(f"Tax Rate: {config.tax_rate} ({float(config.tax_rate) * 100}%)")
    total = config.price * (Decimal("1") + config.tax_rate)
    print(f"Total with tax: ${total:.2f}\n")

    # Datetime
    print(f"Created at: {config.created_at}")
    print(f"  - ISO format: {config.created_at.isoformat()}\n")

    # Timedelta
    print(f"Cache TTL: {config.cache_ttl}")
    print(f"  - Total seconds: {config.cache_ttl.total_seconds()}")
    print(f"Timeout: {config.timeout}")
    print(f"  - Total seconds: {config.timeout.total_seconds()}\n")

    # SecretStr - hides values in logs
    print(f"API Key (hidden): {config.api_key}")
    print(f"API Key (repr): {config.api_key!r}")
    print(f"API Key (actual): {config.api_key.get_secret_value()}\n")

    # JSON types - automatically parsed
    print(f"Feature flags: {config.feature_flags}")
    print(f"  - Type: {type(config.feature_flags).__name__}")
    print(f"  - New UI enabled: {config.feature_flags['new_ui']}")
    print(f"Allowed roles: {config.allowed_roles}")
    print(f"  - Type: {type(config.allowed_roles).__name__}\n")

    # Collection size validation
    print(f"Backup servers: {config.backup_servers}")
    print(f"  - Count: {len(config.backup_servers)}\n")

    print("All types working correctly! ✓")
