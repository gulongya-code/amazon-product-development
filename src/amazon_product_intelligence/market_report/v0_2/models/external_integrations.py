"""Optional external-integration attachment registry for Market Report V0.2."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from amazon_product_intelligence.contracts import deterministic_id

from ..version import EXTERNAL_INTEGRATIONS_CONTRACT_VERSION
from .common import Availability, MarketReportV0_2ValidationError, V0_2Contract, identity, text, texts


class ExternalIntegrationState(StrEnum):
    NOT_ATTACHED = "NOT_ATTACHED"
    ATTACHED = "ATTACHED"


@dataclass(frozen=True, slots=True, kw_only=True)
class ExternalIntegrationAttachment(V0_2Contract):
    attachment_id: str
    integration_name: str
    integration_version: str
    availability: Availability
    external_reference_id: str
    provenance_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("integration_name", "integration_version", "external_reference_id"):
            text(getattr(self, name), f"ExternalIntegrationAttachment.{name}")
        if not isinstance(self.availability, Availability):
            raise MarketReportV0_2ValidationError("external attachment availability is invalid")
        limitations = texts(self.limitations, "external attachment limitations")
        if self.availability is not Availability.AVAILABLE and not limitations:
            raise MarketReportV0_2ValidationError("partial/unavailable attachment requires limitations")
        object.__setattr__(self, "provenance_reference_ids", texts(self.provenance_reference_ids, "external attachment provenance", allow_empty=False))
        object.__setattr__(self, "limitations", limitations)
        if self.attachment_id != identity("market-report-v0.2-external-attachment", self, "attachment_id"):
            raise MarketReportV0_2ValidationError("external attachment ID does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class ExternalIntegrationsRegistry(V0_2Contract):
    registry_id: str
    contract_version: str
    state: ExternalIntegrationState
    attachments: tuple[ExternalIntegrationAttachment, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.contract_version != EXTERNAL_INTEGRATIONS_CONTRACT_VERSION:
            raise MarketReportV0_2ValidationError("unsupported external-integration registry version")
        if not isinstance(self.state, ExternalIntegrationState):
            raise MarketReportV0_2ValidationError("external-integration state is invalid")
        attachments = tuple(sorted(self.attachments, key=lambda item: (item.integration_name, item.attachment_id)))
        if any(not isinstance(item, ExternalIntegrationAttachment) for item in attachments):
            raise MarketReportV0_2ValidationError("external registry contains an invalid attachment")
        if len({item.attachment_id for item in attachments}) != len(attachments):
            raise MarketReportV0_2ValidationError("external attachment IDs must be unique")
        if self.state is ExternalIntegrationState.NOT_ATTACHED and attachments:
            raise MarketReportV0_2ValidationError("NOT_ATTACHED external registry must be empty")
        if self.state is ExternalIntegrationState.ATTACHED and not attachments:
            raise MarketReportV0_2ValidationError("ATTACHED external registry requires an attachment")
        object.__setattr__(self, "attachments", attachments)
        object.__setattr__(self, "limitations", texts(self.limitations, "external registry limitations"))
        if self.registry_id != identity("market-report-v0.2-external-integrations", self, "registry_id"):
            raise MarketReportV0_2ValidationError("external registry ID does not match content")

    @property
    def keyword_attached(self) -> bool:
        return any(item.integration_name == "keyword-intelligence" for item in self.attachments)


def build_external_attachment(**content: Any) -> ExternalIntegrationAttachment:
    content["provenance_reference_ids"] = tuple(sorted(content["provenance_reference_ids"]))
    content["limitations"] = tuple(sorted(content["limitations"]))
    return ExternalIntegrationAttachment(attachment_id=deterministic_id("market-report-v0.2-external-attachment", content), **content)


def build_external_integrations(**content: Any) -> ExternalIntegrationsRegistry:
    normalized = dict(content)
    normalized["attachments"] = tuple(sorted(normalized.get("attachments", ()), key=lambda item: (item.integration_name, item.attachment_id)))
    normalized["limitations"] = tuple(sorted(normalized.get("limitations", ())))
    material = {"contract_version": EXTERNAL_INTEGRATIONS_CONTRACT_VERSION, **normalized}
    return ExternalIntegrationsRegistry(registry_id=deterministic_id("market-report-v0.2-external-integrations", material), **material)


__all__ = (
    "ExternalIntegrationAttachment", "ExternalIntegrationState", "ExternalIntegrationsRegistry",
    "build_external_attachment", "build_external_integrations",
)
