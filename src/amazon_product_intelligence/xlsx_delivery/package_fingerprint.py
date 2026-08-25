"""Compression-independent fingerprints for OOXML package content."""

from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree


class OoxmlPackageFingerprintError(ValueError):
    """Raised when a workbook is not a safe, unambiguous OOXML package."""


def _logical_member(name: str, content: bytes) -> bytes:
    if name != "docProps/core.xml":
        return content
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as exc:
        raise OoxmlPackageFingerprintError("invalid OOXML core properties XML") from exc
    for item in root.iter():
        if item.tag.rsplit("}", 1)[-1] in {"created", "modified"}:
            item.text = None
    return ElementTree.tostring(root, encoding="utf-8")


def ooxml_package_content_sha256(source: bytes | bytearray | Path) -> str:
    """Hash member names and uncompressed bytes, ignoring ZIP encoding details."""

    payload = source.read_bytes() if isinstance(source, Path) else bytes(source)
    try:
        with ZipFile(BytesIO(payload), "r") as package:
            names = package.namelist()
            if len(names) != len(set(names)):
                raise OoxmlPackageFingerprintError(
                    "OOXML package contains duplicate member names"
                )
            if "[Content_Types].xml" not in names or "xl/workbook.xml" not in names:
                raise OoxmlPackageFingerprintError("not an XLSX OOXML package")
            members = [
                {
                    "name": name,
                    "content_sha256": sha256(
                        _logical_member(name, package.read(name))
                    ).hexdigest(),
                }
                for name in sorted(names)
                if not name.endswith("/")
            ]
    except BadZipFile as exc:
        raise OoxmlPackageFingerprintError("invalid OOXML ZIP package") from exc
    canonical = json.dumps(
        members, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


__all__ = ("OoxmlPackageFingerprintError", "ooxml_package_content_sha256")
