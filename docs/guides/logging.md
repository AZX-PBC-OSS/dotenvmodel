# Logging

dotenvmodel logs through Python's standard `logging` module under the `"dotenvmodel"` logger. With no logging setup, warnings and errors surface on stderr via Python's last-resort handler — for example, the `No .env files found` warning. Call `configure_logging()` for the INFO/DEBUG detail (which files were read, how each field resolved) and formatted output.

## Enabling Logging

Use `configure_logging()` to enable logging at a specific level:

```python
from dotenvmodel import configure_logging, DotEnvConfig, Field

# Enable INFO level logging
configure_logging("INFO")


class Config(DotEnvConfig):
    database_url: str = Field()


config = Config.load()
```

## Log Levels

```python
# DEBUG - Most verbose, shows all operations including file searches
configure_logging("DEBUG")

# INFO - Shows file loading and configuration status
configure_logging("INFO")

# WARNING - Only shows warnings (e.g., missing .env files)
configure_logging("WARNING")

# ERROR - Only shows errors
configure_logging("ERROR")
```

!!! info "Default level"

    `configure_logging()` uses `WARNING` when called with no level and no `DOTENVMODEL_LOG_LEVEL` environment variable set. Warnings and errors surface even with no setup at all (via Python's last-resort handler); `configure_logging()` is what adds INFO/DEBUG detail and the formatted output.

## Log Output Example

Here's what you'll see at `INFO` level when loading configuration:

```text
2025-12-05 00:33:40,312 - dotenvmodel - INFO - Loading Config configuration
2025-12-05 00:33:40,312 - dotenvmodel - INFO - Loading configuration for environment: dev
2025-12-05 00:33:40,312 - dotenvmodel - INFO - Reading .env file: /home/user/myapp/.env
2025-12-05 00:33:40,313 - dotenvmodel - INFO - Reading .env file: /home/user/myapp/.env.dev
2025-12-05 00:33:40,313 - dotenvmodel - INFO - Successfully loaded 2 file(s): /home/user/myapp/.env, /home/user/myapp/.env.dev
2025-12-05 00:33:40,313 - dotenvmodel - INFO - Config configuration loaded successfully
```

Logged file paths are always absolute — `resolve_env_dir()` records the base directory as an absolute path, so the log names exactly which files were read.

At `DEBUG` level, you'll also see messages about files that were searched but not found:

```text
2025-12-05 00:33:40,312 - dotenvmodel - DEBUG - /home/user/myapp/.env.local not found (skipping)
2025-12-05 00:33:40,313 - dotenvmodel - DEBUG - /home/user/myapp/.env.dev.local not found (skipping)
```

## Using Environment Variables

`DOTENVMODEL_LOG_LEVEL` is read by `configure_logging()`: set it to choose the level `configure_logging()` applies when called without an explicit level. Call `configure_logging()` once in your entry point, then control verbosity from the environment:

```bash
export DOTENVMODEL_LOG_LEVEL=DEBUG
python your_app.py
```

```bash
# One-off for a single command
DOTENVMODEL_LOG_LEVEL=INFO python your_app.py
```

!!! note "The env var needs `configure_logging()`"

    `DOTENVMODEL_LOG_LEVEL` is only read inside `configure_logging()` — setting it alone, with no logging setup anywhere, changes nothing: warnings and errors still surface via the last-resort handler, exactly as before.

## Custom Format String

Customize the log message format with `format_string`:

```python
from dotenvmodel import configure_logging

# Compact format
configure_logging("INFO", format_string="[%(levelname)s] %(message)s")

# Output: [INFO] Loading Config configuration
```

```python
# Include logger name only
configure_logging("DEBUG", format_string="%(name)s :: %(levelname)s :: %(message)s")

# Output: dotenvmodel :: DEBUG :: .env.local not found (skipping)
```

The default format is:

```text
%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

## Custom Handler

Provide a custom logging handler for advanced use cases (e.g., writing to a file):

```python
import logging
from dotenvmodel import configure_logging

# Log to a file instead of stdout
handler = logging.FileHandler("dotenvmodel.log")
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

configure_logging("DEBUG", handler=handler)
```

!!! note "Default handler"

    When `handler` is `None` (default), dotenvmodel uses a `StreamHandler` writing to `stdout`.

## Disabling Logging

Use `disable_logging()` to turn off all dotenvmodel log output:

```python
from dotenvmodel import disable_logging

# Turn off all dotenvmodel logs
disable_logging()
```

This is useful after temporarily enabling logging for debugging:

```python
from dotenvmodel import configure_logging, disable_logging

# Enable for debugging
configure_logging("DEBUG")
config = AppConfig.load()

# Disable after debugging
disable_logging()
```

## Using the Standard Logging Module Directly

dotenvmodel uses a named logger (`"dotenvmodel"`) that integrates with Python's standard `logging` module. You can configure it directly for full control:

```python
import logging
from dotenvmodel import LOGGER_NAME

# Get the dotenvmodel logger
logger = logging.getLogger(LOGGER_NAME)
logger.setLevel(logging.DEBUG)

# Add a custom handler
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(handler)

# Prevent propagation to root logger
logger.propagate = False
```

### Integration with Application Logging

For structured logging or log aggregation (e.g., in FastAPI/gunicorn):

```python
import logging
import json
from dotenvmodel import LOGGER_NAME


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "logger": record.name,
                "level": record.levelname,
                "message": record.getMessage(),
            }
        )


handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())

logger = logging.getLogger(LOGGER_NAME)
logger.setLevel(logging.DEBUG)  # without this, INFO/DEBUG records never reach the formatter
logger.addHandler(handler)
```

Without an explicit `setLevel()`, the logger's effective level is inherited from the root logger (`WARNING` by default), so INFO/DEBUG records are dropped before they ever reach the `JsonFormatter`.

!!! tip "Logger name"

    The logger name is available as `LOGGER_NAME` (value: `"dotenvmodel"`). Use this constant to avoid hardcoding the string.

## See Also

- [Logging Config API Reference](../api-reference/logging-config.md) — `configure_logging()`, `disable_logging()`, `LOGGER_NAME`
- [Loading Configuration](loading.md) — What gets logged during the loading process
