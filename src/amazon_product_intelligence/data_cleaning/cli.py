"""Explicit offline/live entry point for the governed Data Cleaning V1 flow."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping, TextIO

from amazon_product_intelligence.connectors import (
    BoundedTransientRetryPolicy,
    HttpJsonTransport,
    ProviderConfig,
    ProviderConnectorError,
    ProviderErrorCode,
    ProviderRegistry,
    TransportRequest,
    TransportResponse,
    XiYouProvider,
)
from amazon_product_intelligence.connectors.sorftime_legacy import (
    LegacySorftimeFixtureProvider,
)
from amazon_product_intelligence.contracts import deterministic_id
from amazon_product_intelligence.normalization import CanonicalNormalizationPipeline

from .models import DataCleaningRequest
from .service import DataCleaningService


_FIXTURE_TIME = "2025-01-15T00:00:00+00:00"
_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_FIXTURES = {
    ("xiyou", "asin_info"): _REPOSITORY_ROOT
    / "tests"
    / "fixtures"
    / "data_cleaning_v0_1"
    / "xiyou_asin_info_http_v2.json",
    ("sorftime", "product_detail"): _REPOSITORY_ROOT
    / "tests"
    / "fixtures"
    / "data_cleaning_v0_1"
    / "sorftime_product_detail.json",
}
_DEFAULT_INPUTS: Mapping[tuple[str, str], Mapping[str, Any]] = {
    ("xiyou", "asin_info"): {
        "entities": [{"country": "US", "asin": "B0G2VV4RBW"}],
    },
    ("sorftime", "product_detail"): {
        "amz_site": "US",
        "asin": "B0G2VV4RBW",
    },
}
_CREDENTIAL_ENVIRONMENTS = {
    "xiyou": "XIYOU_API_KEY",
    "sorftime": "SORFTIME_API_KEY",
}


class StaticJsonTransport:
    """Offline transport that returns one already-sanitized fixture payload."""

    def __init__(self, operation: str, payload: Any) -> None:
        self._operation = operation
        self._payload = payload

    def execute(self, request: TransportRequest) -> TransportResponse:
        if request.operation != self._operation:
            raise ProviderConnectorError(
                ProviderErrorCode.FIELD_UNAVAILABLE,
                "fixture does not cover the requested provider operation",
                provider_id=request.provider_id,
                operation=request.operation,
            )
        return TransportResponse(status_code=200, payload=self._payload)


class UnsupportedLiveTransport:
    """Fail closed where no audited production HTTP endpoint exists."""

    def execute(self, request: TransportRequest) -> TransportResponse:
        raise ProviderConnectorError(
            ProviderErrorCode.PROVIDER_UNAVAILABLE,
            "provider has no audited production HTTP endpoint contract",
            provider_id=request.provider_id,
            operation=request.operation,
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="amazon-data-cleaning")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--fixture", action="store_true", help="run with a local sanitized fixture")
    mode.add_argument("--live", action="store_true", help="explicitly allow a production request")
    parser.add_argument("--provider", required=True)
    parser.add_argument("--operation", required=True)
    parser.add_argument("--input-json")
    parser.add_argument("--fixture-file", type=Path)
    parser.add_argument("--marketplace", default="US")
    parser.add_argument("--locale", default="en-us")
    parser.add_argument("--currency", default="USD")
    parser.add_argument("--output", choices=("summary", "json"), default="summary")
    return parser


def _load_fixture(provider: str, operation: str, fixture_file: Path | None) -> Any:
    path = fixture_file or _FIXTURES.get((provider, operation))
    if path is None:
        raise ProviderConnectorError(
            ProviderErrorCode.FIELD_UNAVAILABLE,
            "no sanitized fixture is registered for the provider operation",
            provider_id=provider,
            operation=operation,
        )
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProviderConnectorError(
            ProviderErrorCode.BAD_RESPONSE,
            "fixture could not be read as JSON",
            provider_id=provider,
            operation=operation,
        ) from exc


def _provider(provider_id: str, transport: Any, environment: Mapping[str, str]) -> Any:
    factories = {
        "xiyou": lambda: XiYouProvider(
            transport,
            environment=environment,
            retry_policy=BoundedTransientRetryPolicy(),
        ),
        "sorftime": lambda: LegacySorftimeFixtureProvider(
            transport,
            fixture_only=isinstance(transport, StaticJsonTransport),
            environment=environment,
            retry_policy=BoundedTransientRetryPolicy(),
        ),
    }
    factory = factories.get(provider_id)
    if factory is None:
        raise ProviderConnectorError(
            ProviderErrorCode.PROVIDER_NOT_REGISTERED,
            "requested provider is not registered",
            provider_id=provider_id,
        )
    return factory()


def _registry(
    *,
    provider_id: str,
    fixture: bool,
    operation: str,
    fixture_file: Path | None,
    environment: Mapping[str, str],
) -> ProviderRegistry:
    if fixture:
        payload = _load_fixture(provider_id, operation, fixture_file)
        transport: Any = StaticJsonTransport(operation, payload)
        provider_environment = {
            _CREDENTIAL_ENVIRONMENTS.get(provider_id, "FIXTURE_CREDENTIAL"): "fixture-only",
        }
        max_attempts = 1
    else:
        transports = {
            "xiyou": lambda: HttpJsonTransport({"xiyou": "https://openapi.xydc.com"}),
            "sorftime": UnsupportedLiveTransport,
        }
        transport_factory = transports.get(provider_id)
        if transport_factory is None:
            raise ProviderConnectorError(
                ProviderErrorCode.PROVIDER_NOT_REGISTERED,
                "requested provider is not registered",
                provider_id=provider_id,
            )
        transport = transport_factory()
        provider_environment = environment
        max_attempts = 3
    provider = _provider(provider_id, transport, provider_environment)
    credential_env = _CREDENTIAL_ENVIRONMENTS.get(provider_id)
    registry = ProviderRegistry()
    registry.register(
        provider,
        ProviderConfig(
            provider_id=provider_id,
            enabled=True,
            priority=1,
            credential_env=credential_env,
            timeout_seconds=10.0,
            max_attempts=max_attempts,
        ),
    )
    return registry


def _request(args: argparse.Namespace, parameters: Mapping[str, Any]) -> DataCleaningRequest:
    observed_at = (
        _FIXTURE_TIME
        if args.fixture
        else datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    material = {
        "provider": args.provider,
        "operation": args.operation,
        "parameters": parameters,
        "marketplace": args.marketplace,
        "retrieved_at": observed_at,
    }
    collection_run_id = deterministic_id("collection", material)
    normalization_run_id = deterministic_id(
        "normalization",
        {"collection_run_id": collection_run_id, "version": "canonical-normalization-v0.1"},
    )
    return DataCleaningRequest(
        provider_id=args.provider,
        operation=args.operation,
        parameters=parameters,
        marketplace=args.marketplace.strip().upper(),
        locale=args.locale.strip().lower(),
        retrieved_at=observed_at,
        transformed_at=observed_at,
        collection_run_id=collection_run_id,
        normalization_run_id=normalization_run_id,
        normalized_at=observed_at,
        currency=args.currency.strip().upper() if args.currency else None,
    )


def _error_payload(error: ProviderConnectorError) -> dict[str, Any]:
    status = "BLOCKED_CONFIGURATION" if error.code is ProviderErrorCode.CONFIGURATION else "FAILED"
    return {
        "status": status,
        "error": {
            "code": error.code.value,
            "message": str(error),
            "provider_id": error.provider_id,
            "operation": error.operation,
            "retryable": error.retryable,
        },
    }


def run(
    argv: list[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    stdout: TextIO | None = None,
) -> int:
    output = sys.stdout if stdout is None else stdout
    args = _parser().parse_args(argv)
    environment = os.environ if environ is None else environ
    try:
        if args.input_json is not None:
            parameters = json.loads(args.input_json)
        else:
            parameters = dict(_DEFAULT_INPUTS.get((args.provider, args.operation), {}))
        if not isinstance(parameters, dict):
            raise ValueError("input JSON must be an object")
        registry = _registry(
            provider_id=args.provider,
            fixture=args.fixture,
            operation=args.operation,
            fixture_file=args.fixture_file,
            environment=environment,
        )
        result = DataCleaningService(
            registry,
            CanonicalNormalizationPipeline.with_defaults(),
        ).clean(_request(args, parameters))
    except ProviderConnectorError as exc:
        output.write(json.dumps(_error_payload(exc), ensure_ascii=False, sort_keys=True) + "\n")
        return 2
    except (ValueError, json.JSONDecodeError) as exc:
        payload = {
            "status": "FAILED",
            "error": {"code": "INVALID_INPUT", "message": str(exc)},
        }
        output.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
        return 2

    payload = (
        result.to_dict()
        if args.output == "json"
        else {
            "run_id": result.run_id,
            "provider": result.provider,
            "operation": result.operation,
            "status": result.status.value,
            **result.quality_summary.to_dict(),
        }
    )
    output.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    return 0


def main() -> None:
    raise SystemExit(run())


__all__ = ("StaticJsonTransport", "main", "run")
