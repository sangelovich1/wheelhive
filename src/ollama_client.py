"""
Ollama Client

Reusable client for querying Ollama server information.
Can be used from CLI, bot, or any other component.

Copyright (c) 2025 Steve Angelovich
Licensed under the MIT License - see LICENSE file for details.
"""

import json
import logging
from collections.abc import Generator
from typing import Any

import requests

import constants as const
from system_settings import get_settings


logger = logging.getLogger(__name__)


class OllamaClient:
    """
    Client for interacting with Ollama server API

    Provides methods to query available models, server status, and model details.
    """

    def __init__(self, base_url: str | None = None):
        """
        Initialize Ollama client

        Args:
            base_url: Ollama server URL (None = use system settings)
        """
        if base_url is None:
            settings = get_settings()
            base_url = settings.get(const.SETTING_OLLAMA_BASE_URL, "http://localhost:11434")
        self.base_url = base_url
        logger.debug(f"OllamaClient initialized with base_url={self.base_url}")

    def list_models(self, timeout: int = 10) -> list[dict[str, Any]]:
        """
        List all available models on Ollama server

        Args:
            timeout: Request timeout in seconds

        Returns:
            List of model dictionaries with keys: name, size, modified_at, digest

        Raises:
            requests.RequestException: If connection fails
        """
        try:
            url = f"{self.base_url}/api/tags"
            logger.debug(f"Fetching models from {url}")

            response = requests.get(url, timeout=timeout)
            response.raise_for_status()

            data: dict[str, Any] = response.json()
            models: list[dict[str, Any]] = data.get("models", [])

            logger.info(f"Found {len(models)} models on Ollama server")
            return models

        except requests.exceptions.Timeout:
            logger.error(f"Timeout connecting to Ollama server at {self.base_url}")
            raise
        except requests.exceptions.ConnectionError:
            logger.error(f"Could not connect to Ollama server at {self.base_url}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching Ollama models: {e}")
            raise

    def list_vision_models(self, timeout: int = 10) -> list[dict[str, Any]]:
        """
        List vision-capable models (llava, minicpm-v, etc.)

        Args:
            timeout: Request timeout in seconds

        Returns:
            List of vision model dictionaries
        """
        all_models = self.list_models(timeout=timeout)

        # Filter for known vision model names
        vision_keywords = ["llava", "vision", "minicpm", "bakllava", "moondream"]

        vision_models = [
            model for model in all_models
            if any(keyword in model.get("name", "").lower() for keyword in vision_keywords)
        ]

        logger.info(f"Found {len(vision_models)} vision models out of {len(all_models)} total")
        return vision_models

    def get_model_info(self, model_name: str, timeout: int = 10) -> dict[str, Any] | None:
        """
        Get detailed information about a specific model

        Args:
            model_name: Name of the model (e.g., "llava:13b")
            timeout: Request timeout in seconds

        Returns:
            Model info dictionary or None if not found
        """
        try:
            url = f"{self.base_url}/api/show"
            payload = {"name": model_name}

            logger.debug(f"Fetching info for model {model_name}")

            response = requests.post(url, json=payload, timeout=timeout)
            response.raise_for_status()

            result: dict[str, Any] = response.json()
            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching model info for {model_name}: {e}")
            return None

    def is_available(self, timeout: int = 5) -> bool:
        """
        Check if Ollama server is available

        Args:
            timeout: Request timeout in seconds

        Returns:
            True if server is reachable, False otherwise
        """
        try:
            url = f"{self.base_url}/api/tags"
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException:
            return False

    def format_model_size(self, size_bytes: int) -> str:
        """
        Format model size in human-readable format

        Args:
            size_bytes: Size in bytes

        Returns:
            Formatted string (e.g., "4.7 GB")
        """
        if size_bytes < 1024:
            return f"{size_bytes} B"
        if size_bytes < 1024**2:
            return f"{size_bytes / 1024:.1f} KB"
        if size_bytes < 1024**3:
            return f"{size_bytes / (1024**2):.1f} MB"
        return f"{size_bytes / (1024**3):.1f} GB"

    def pull_model(self, model_name: str, stream: bool = True, timeout: int = 600) -> Generator[dict[str, Any], None, bool]:
        """
        Pull (download) a model from Ollama registry

        Args:
            model_name: Name of the model to pull (e.g., "llama3.2-vision:11b")
            stream: If True, stream progress updates; if False, wait for completion
            timeout: Request timeout in seconds (default 10 minutes for large models)

        Returns:
            True if successful, False otherwise

        Yields:
            Progress updates if stream=True (dict with status, total, completed)
        """
        try:
            url = f"{self.base_url}/api/pull"
            payload = {"name": model_name, "stream": stream}

            logger.info(f"Pulling model {model_name} from Ollama registry")

            if stream:
                # Stream progress updates
                response = requests.post(url, json=payload, stream=True, timeout=timeout)
                response.raise_for_status()

                for line in response.iter_lines():
                    if line:
                        try:
                            progress = json.loads(line)
                            yield progress
                        except json.JSONDecodeError:
                            logger.warning(f"Could not parse progress line: {line}")
                            continue

                logger.info(f"Successfully pulled model {model_name}")
                return True

            else:
                # Wait for completion
                response = requests.post(url, json=payload, timeout=timeout)
                response.raise_for_status()
                logger.info(f"Successfully pulled model {model_name}")
                return True

        except requests.exceptions.Timeout:
            logger.error(f"Timeout pulling model {model_name} after {timeout}s")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Error pulling model {model_name}: {e}")
            return False

    def delete_model(self, model_name: str, timeout: int = 30) -> bool:
        """
        Delete a model from local storage

        Args:
            model_name: Name of the model to delete
            timeout: Request timeout in seconds

        Returns:
            True if successful, False otherwise
        """
        try:
            url = f"{self.base_url}/api/delete"
            payload = {"name": model_name}

            logger.info(f"Deleting model {model_name}")

            response = requests.delete(url, json=payload, timeout=timeout)
            response.raise_for_status()

            logger.info(f"Successfully deleted model {model_name}")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"Error deleting model {model_name}: {e}")
            return False


# Module-level convenience functions
def list_ollama_models(base_url: str | None = None) -> list[dict[str, Any]]:
    """
    Convenience function to list all Ollama models

    Args:
        base_url: Ollama server URL (None = use system settings)

    Returns:
        List of model dictionaries
    """
    client = OllamaClient(base_url=base_url)
    return client.list_models()


def list_vision_models(base_url: str | None = None) -> list[dict[str, Any]]:
    """
    Convenience function to list vision-capable Ollama models

    Args:
        base_url: Ollama server URL (None = use system settings)

    Returns:
        List of vision model dictionaries
    """
    client = OllamaClient(base_url=base_url)
    return client.list_vision_models()


def check_ollama_available(base_url: str | None = None) -> bool:
    """
    Check if Ollama server is available

    Args:
        base_url: Ollama server URL (None = use system settings)

    Returns:
        True if available, False otherwise
    """
    client = OllamaClient(base_url=base_url)
    return client.is_available()
