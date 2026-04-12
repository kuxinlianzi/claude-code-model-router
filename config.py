#!/usr/bin/env python3
"""
Configuration loader for Model Router

Supports loading from:
1. YAML file (config.yaml) - highest priority
2. Environment variables (MODEL_ROUTER_*) - medium priority
3. Default values (code-defined) - lowest priority

Environment variable mapping:
    MODEL_ROUTER_SERVER_HOST      -> server.host
    MODEL_ROUTER_JUDGE_MODEL      -> judge.model
    MODEL_ROUTER_DASHSCOPE_API_KEY-> dashscope.api_key
    ...etc
"""

import os
from pathlib import Path
from typing import Any, Optional

try:
    import yaml
except ImportError:
    print("[WARN] PyYAML not installed, running with defaults.")
    print("Install with: pip install pyyaml")
    yaml = None


class ConfigError(Exception):
    """Raised when configuration is invalid."""
    pass


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge two dicts, with override taking precedence."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _get_env_value(key: str, default: Any = None) -> Any:
    """Get environment variable value, applying basic type conversion."""
    value = os.environ.get(key)
    if value is None:
        return default

    # Try boolean
    if value.lower() in ('true', 'yes', '1'):
        return True
    if value.lower() in ('false', 'no', '0'):
        return False

    # Try number
    try:
        if '.' in value:
            return float(value)
        return int(value)
    except ValueError:
        pass

    return value


def _load_from_env(env_prefix: str = "MODEL_ROUTER_") -> dict:
    """Load configuration from environment variables."""
    config = {}

    # Define the mapping structure
    env_mappings = [
        ("SERVER_HOST", "server.host"),
        ("SERVER_PORT", "server.port"),
        ("JUDGE_MODEL", "judge.model"),
        ("OLLAMA_HOST", "judge.ollama_host"),
        ("OLLAMA_PORT", "judge.ollama_port"),
        ("JUDGE_TIMEOUT", "judge.timeout"),
        ("TRAUNCATE_LIMIT", "judge.truncate_limit"),  # Note: typo preserved for backward compat
        ("ROUTING_CHEAP_MODEL", "routing.cheap_model"),
        ("ROUTING_EXPENSIVE_MODEL", "routing.expensive_model"),
        ("ROUTING_THRESHOLD", "routing.threshold"),
        ("DASHSCOPE_API_KEY", "dashscope.api_key"),
        ("DASHSCOPE_BASE_URL", "dashscope.base_url"),
        ("MAX_CONNECTIONS", "client.max_connections"),
        ("MAX_KEEPALIVE", "client.max_keepalive_connections"),
        ("KEEPALIVE_EXPIRY", "client.keepalive_expiry"),
        ("DEFAULT_TIMEOUT", "client.default_timeout"),
    ]

    for env_key, config_path in env_mappings:
        full_env_key = f"{env_prefix}{env_key}"
        value = _get_env_value(full_env_key)

        if value is not None:
            # Navigate to nested key
            keys = config_path.split(".")
            d = config
            for key in keys[:-1]:
                if key not in d:
                    d[key] = {}
                d = d[key]
            d[keys[-1]] = value

    return config


def _load_yaml_file(file_path: Path) -> dict:
    """Load configuration from YAML file."""
    if yaml is None:
        return {}

    if not file_path.exists():
        return {}

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = yaml.safe_load(f)
            return content or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in {file_path}: {e}")
    except Exception as e:
        raise ConfigError(f"Failed to read {file_path}: {e}")


# Default configuration - never modified by user
DEFAULT_CONFIG = {
    "server": {
        "host": "localhost",
        "port": 8888,
    },
    "judge": {
        "model": "qwen3.5:2b",
        "ollama_host": "localhost",
        "ollama_port": 11434,
        "timeout": 8,
        "truncate_limit": 2000,
    },
    "routing": {
        "cheap_model": "qwen3.5-flash",
        "expensive_model": "qwen3.6-plus",
        "threshold": 6,
    },
    "dashscope": {
        "api_key": "",
        "base_url": "https://dashscope.aliyuncs.com/apps/anthropic",
    },
    "client": {
        "max_connections": 100,
        "max_keepalive_connections": 20,
        "keepalive_expiry": 60.0,
        "default_timeout": 60.0,
    },
}


class Config:
    """Global configuration object."""

    def __init__(self, config_file: Optional[Path] = None):
        """Initialize configuration from file and environment variables."""
        if config_file is None:
            # Try common locations
            candidates = [
                Path("config.yaml"),           # Project root
                Path("./config.yaml"),         # Relative
                Path("/etc/model-router/config.yaml"),  # System-wide (Linux)
            ]

            for candidate in candidates:
                if candidate.exists():
                    config_file = candidate
                    break

        # Load configs in order of priority (lowest to highest)
        merged_config = DEFAULT_CONFIG.copy()

        # 1. YAML file (if exists)
        if config_file:
            yaml_config = _load_yaml_file(config_file)
            merged_config = _deep_merge(merged_config, yaml_config)

        # 2. Environment variables (override everything)
        env_config = _load_from_env()
        merged_config = _deep_merge(merged_config, env_config)

        # Store merged config
        self._config = merged_config

        # Validate critical settings
        self._validate()

    def _validate(self):
        """Validate required configuration settings."""
        if not self.dashscope_api_key:
            raise ConfigError(
                "DashScope API key is required.\n"
                "Set it in one of these ways:\n"
                "  1. Add DASHSCOPE_API_KEY to config.yaml\n"
                "  2. Set DASHSCOPE_API_KEY environment variable"
            )

    # Property accessors for clean configuration access

    @property
    def server_host(self) -> str:
        return self._config["server"]["host"]

    @property
    def server_port(self) -> int:
        return self._config["server"]["port"]

    @property
    def judge_model(self) -> str:
        return self._config["judge"]["model"]

    @property
    def ollama_host(self) -> str:
        return self._config["judge"]["ollama_host"]

    @property
    def ollama_port(self) -> int:
        return self._config["judge"]["ollama_port"]

    @property
    def ollama_timeout(self) -> int:
        return self._config["judge"]["timeout"]

    @property
    def truncate_limit(self) -> int:
        return self._config["judge"]["truncate_limit"]

    @property
    def cheap_model(self) -> str:
        return self._config["routing"]["cheap_model"]

    @property
    def expensive_model(self) -> str:
        return self._config["routing"]["expensive_model"]

    @property
    def threshold(self) -> int:
        return self._config["routing"]["threshold"]

    @property
    def dashscope_api_key(self) -> str:
        return self._config["dashscope"]["api_key"]

    @property
    def dashscope_base_url(self) -> str:
        return self._config["dashscope"]["base_url"]

    @property
    def max_connections(self) -> int:
        return self._config["client"]["max_connections"]

    @property
    def max_keepalive_connections(self) -> int:
        return self._config["client"]["max_keepalive_connections"]

    @property
    def keepalive_expiry(self) -> float:
        return self._config["client"]["keepalive_expiry"]

    @property
    def default_timeout(self) -> float:
        return self._config["client"]["default_timeout"]

    def get_ollama_url(self, endpoint: str = "/api/generate") -> str:
        """Construct Ollama API URL."""
        return f"http://{self.ollama_host}:{self.ollama_port}{endpoint}"

    def get_dashscope_url(self, path: str = "/v1/messages") -> str:
        """Construct DashScope API URL."""
        return f"{self.dashscope_base_url}{path}"

    def __repr__(self) -> str:
        return (
            f"Config(host={self.server_host}, port={self.server_port}, "
            f"judge_model={self.judge_model}, "
            f"cheap_model={self.cheap_model}, expensive_model={self.expensive_model})"
        )


# Global config instance
_config_instance: Optional[Config] = None


def get_config(config_file: Optional[Path] = None) -> Config:
    """Get global configuration instance."""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config(config_file)
    return _config_instance


def reset_config():
    """Reset global configuration (useful for testing)."""
    global _config_instance
    _config_instance = None


__all__ = ["Config", "get_config", "reset_config", "ConfigError"]
