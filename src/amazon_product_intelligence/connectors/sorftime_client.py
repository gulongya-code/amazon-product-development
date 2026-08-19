"""Low-level Sorftime API client foundation."""

from __future__ import annotations

import logging

from .base_client import BaseAPIClient
from .transport import ProviderTransport


class SorftimeClient(BaseAPIClient):
    """Sorftime client with no guessed business endpoints or embedded secrets."""

    def __init__(
        self,
        *,
        transport: ProviderTransport | None = None,
        timeout_seconds: float = 10.0,
        max_attempts: int = 3,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(
            source="sorftime",
            api_key_env="SORFTIME_API_KEY",
            base_url_env="SORFTIME_API_BASE_URL",
            credential_header="X-Api-Key",
            transport=transport,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
            logger=logger,
        )


__all__ = ("SorftimeClient",)
