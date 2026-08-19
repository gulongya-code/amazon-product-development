"""Low-level XiYou API client foundation."""

from __future__ import annotations

import logging

from .base_client import BaseAPIClient
from .transport import ProviderTransport


class XiyouClient(BaseAPIClient):
    """XiYou client configured only through environment-owned secrets/URLs."""

    def __init__(
        self,
        *,
        transport: ProviderTransport | None = None,
        timeout_seconds: float = 10.0,
        max_attempts: int = 3,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(
            source="xiyou",
            api_key_env="XIYOU_API_KEY",
            base_url_env="XIYOU_API_BASE_URL",
            credential_header="X-Api-Key",
            transport=transport,
            default_headers={"X-Auth-Version": "2.0"},
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
            logger=logger,
        )


XiYouClient = XiyouClient


__all__ = ("XiYouClient", "XiyouClient")
