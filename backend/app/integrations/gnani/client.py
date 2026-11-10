import logging
import os
from typing import Any, Dict, Optional
import httpx
from backend.app.core.config import settings

logger = logging.getLogger("resolvegrid.gnani")


class GnaniIntegrationError(Exception):
    """Base exception for Gnani integrations."""
    pass


class GnaniNotConfiguredError(GnaniIntegrationError):
    """Raised when an operation requires live Gnani API credentials that have not been provided."""
    pass


class GnaniClient:
    """
    Reusable HTTP client for Gnani AI endpoints with timeouts, retries,
    credential management and structured logging.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        token: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_seconds: float = 5.0,
        max_retries: int = 1
    ):
        self.api_key = api_key or settings.GNANI_API_KEY
        self.token = token or settings.GNANI_TOKEN
        self.base_url = base_url
        self.timeout = timeout_seconds
        self.max_retries = max_retries

    @property
    def is_configured(self) -> bool:
        """Returns True if live credentials and base endpoint are provided."""
        return bool(self.api_key or self.token) and bool(self.base_url)

    def _get_headers(self, auth_header_name: str = "X-API-Key-ID") -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if self.api_key:
            headers[auth_header_name] = self.api_key
        return headers

    def _get_auth_headers(self, auth_header_name: str = "X-API-Key-ID") -> Dict[str, str]:
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if self.api_key:
            headers[auth_header_name] = self.api_key
        return headers

    async def post_json(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        custom_headers: Optional[Dict[str, str]] = None,
        auth_header_name: str = "X-API-Key-ID"
    ) -> Dict[str, Any]:
        """Execute a POST request with retry backoff against a Gnani API endpoint."""
        if not self.is_configured:
            raise GnaniNotConfiguredError(
                f"Gnani endpoint '{endpoint}' cannot be reached: credentials or base URL not configured."
            )

        url = self.base_url
        if endpoint:
            url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        headers = self._get_headers(auth_header_name=auth_header_name)
        if custom_headers:
            headers.update(custom_headers)

        last_error = None
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(1, self.max_retries + 1):
                try:
                    logger.info("Calling Gnani API: %s (attempt %d/%d)", url, attempt, self.max_retries)
                    response = await client.post(url, json=payload, headers=headers)
                    response.raise_for_status()
                    return response.json()
                except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                    last_error = exc
                    logger.warning("Gnani API attempt %d failed: %s", attempt, str(exc))
                    if isinstance(exc, httpx.HTTPStatusError) and 400 <= exc.response.status_code < 500:
                        raise GnaniIntegrationError(f"Gnani API client error ({exc.response.status_code}): {exc.response.text}") from exc

        raise GnaniIntegrationError(f"Gnani API request to {url} failed after {self.max_retries} retries: {last_error}")

    async def post_bytes(
        self,
        endpoint: str = "",
        payload: Optional[Dict[str, Any]] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        auth_header_name: str = "X-API-Key-ID"
    ) -> bytes:
        """Execute a POST request returning raw binary bytes (e.g., TTS audio streams)."""
        if not self.is_configured:
            raise GnaniNotConfiguredError(
                f"Gnani endpoint '{endpoint or self.base_url}' cannot be reached: credentials or base URL not configured."
            )

        url = self.base_url
        if endpoint:
            url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"

        headers = self._get_headers(auth_header_name=auth_header_name)
        if custom_headers:
            headers.update(custom_headers)

        last_error = None
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(1, self.max_retries + 1):
                try:
                    logger.info("Calling Gnani API (bytes): %s (attempt %d/%d)", url, attempt, self.max_retries)
                    response = await client.post(url, json=payload, headers=headers)
                    response.raise_for_status()
                    return response.content
                except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                    last_error = exc
                    status_info = f" status={exc.response.status_code}" if isinstance(exc, httpx.HTTPStatusError) else ""
                    logger.warning("Gnani API attempt %d failed:%s %s", attempt, status_info, str(exc))
                    if isinstance(exc, httpx.HTTPStatusError) and 400 <= exc.response.status_code < 500:
                        raise GnaniIntegrationError(f"Gnani API client error ({exc.response.status_code}): {exc.response.text}") from exc

        raise GnaniIntegrationError(f"Gnani API request to {url} failed after {self.max_retries} retries: {last_error}")

    async def post_multipart(
        self,
        endpoint: str = "",
        files: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        auth_header_name: str = "X-API-Key-ID"
    ) -> Dict[str, Any]:
        """Execute a multipart/form-data POST request against a Gnani API endpoint."""
        if not self.is_configured:
            target_desc = endpoint or self.base_url or "unknown"
            raise GnaniNotConfiguredError(
                f"Gnani endpoint '{target_desc}' cannot be reached: credentials or base URL not configured."
            )

        url = self.base_url
        if endpoint:
            url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"

        headers = self._get_auth_headers(auth_header_name=auth_header_name)
        if custom_headers:
            headers.update(custom_headers)

        last_error = None
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(1, self.max_retries + 1):
                try:
                    logger.info("Calling Gnani API (multipart): %s (attempt %d/%d)", url, attempt, self.max_retries)
                    response = await client.post(url, files=files, data=data, headers=headers)
                    response.raise_for_status()
                    return response.json()
                except (httpx.RequestError, httpx.HTTPStatusError) as exc:
                    last_error = exc
                    status_info = f" status={exc.response.status_code}" if isinstance(exc, httpx.HTTPStatusError) else ""
                    logger.warning("Gnani API attempt %d failed:%s %s", attempt, status_info, str(exc))
                    if isinstance(exc, httpx.HTTPStatusError) and 400 <= exc.response.status_code < 500:
                        raise GnaniIntegrationError(f"Gnani API client error ({exc.response.status_code}): {exc.response.text}") from exc

        raise GnaniIntegrationError(f"Gnani API request to {url} failed after {self.max_retries} retries: {last_error}")
