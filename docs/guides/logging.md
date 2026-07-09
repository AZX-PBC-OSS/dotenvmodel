# Logging

dotenvmodel includes optional logging to help debug configuration loading. Logging is disabled by default but can be easily enabled via code or environment variable.

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

    If no level is specified and the `DOTENVMODEL_LOG_LEVEL` environment variable is not set, logging defaults to `WARNING`.

## Log Output Example

Here's what you'll see at `INFO` level when loading configuration:

```text
2025-12-05 00:33:40 - dotenvmodel - INFO - Loading Config configuration
2025-12-05 00:33:40 - dotenvmodel - INFO - Loading configuration for environment: dev
2025-12-05 00:33:40 - dotenvmodel - INFO - Loading environment variables from .env
2025-12-05 00:33:40 - dotenvmodel - INFO - Loading environment variables from .env.dev
2025-12-05 00:33:40 - dotenvmodel - INFO - Successfully loaded 2 file(s): .env, .env.dev
2025-12-05 00:33:40 - dotenvmodel - INFO - Config configuration loaded successfully
```

At `DEBUG` level, you'll also see messages about files that were searched but not found:

```text
2025-12-05 00:33:40 - dotenvmodel - DEBUG - .env.local not found (skipping)
2025-12-05 00:33:40 - dotenvmodel - DEBUG - .env.dev.local not found (skipping)
```

## Using Environment Variables

Enable logging without changing code by setting the `DOTENVMODEL_LOG_LEVEL` environment variable:

```bash
# Set via environment variable
export DOTENVMODEL_LOG_LEVEL=DEBUG
python your_app.py
```

```bash
# One-off for a single command
DOTENVMODEL_LOG_LEVEL=INFO python your_app.py
```

!!! tip "No code changes needed"

    When `DOTENVMODEL_LOG_LEVEL` is set, you don't need to call `configure_logging()` at all. The logger will pick up the level automatically when any logging code runs. However, calling `configure_logging()` without arguments will also respect this env var.

## Custom Format String

Customize the log message format with `format_string`:

```python
from dotenvmodel import configure_logging

# Compact format
configure_logging(
    "INFO",
    format_string="[%(levelname)s] %(message)s"
)

# Output: [INFO] Loading Config configuration
```

```python
# Include logger name only
configure_logging(
    "DEBUG",
    format_string="%(name)s :: %(levelname)s :: %(message)s"
)

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
        return json.dumps({
            "logger": record.name,
            "level": record.levelname,
            "message": record.getMessage(),
        })

handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logging.getLogger(LOGGER_NAME).addHandler(handler)
```

!!! tip "Logger name"

    The logger name is available as `LOGGER_NAME` (value: `"dotenvmodel"`). Use this constant to avoid hardcoding the string.

## See Also

- [Logging Config API Reference](../api-reference/logging-config.md) — `configure_logging()`, `disable_logging()`, `LOGGER_NAME`
- [Loading Configuration](loading.md) — What gets logged during the loading process
