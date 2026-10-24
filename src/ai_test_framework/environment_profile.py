"""Offline environment identity and capability resolution, never write authorization."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from .execution_readiness import _assert_no_sensitive_fields

IDENTITY = ("stage", "zone", "platform", "organization_view_id", "role_id", "build_id")
PLATFORMS = {"web", "app", "h5", "miniapp", "api", "database"}
PROFILE_FIELDS = {"schema_version", "profile_id", "status", *IDENTITY, "capabilities", "reviewed_at", "expires_at"}
OBSERVATION_FIELDS = {"schema_version", *IDENTITY, "capabilities", "observed_at"}
REQUEST_FIELDS = {"schema_version", *IDENTITY, "required_capabilities", "operation"}


def _date(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else None
        return parsed if parsed and parsed.tzinfo else None
    except ValueError:
        return None


def resolve_environment(profile: Any, observation: Any, request: Any, *, now: datetime | None = None) -> dict[str, Any]:
    """Compare reviewed candidate, run request and fresh independent observation.

    All three inputs are local declarations. A passed receipt does NOT attest
    that the observation was made at the real UI or that a write is authorized.
    """
    errors: list[str] = []
    for label, value in (("profile", profile), ("observation", observation), ("request", request)):
        if not isinstance(value, dict):
            errors.append(f"{label}_invalid")
        else:
            try:
                _assert_no_sensitive_fields(value)
            except ValueError:
                errors.append(f"{label}_contains_sensitive_field")
    if errors:
        return {"status": "blocked", "error_codes": sorted(set(errors)), "write_authorized": False}
    assert isinstance(profile, dict) and isinstance(observation, dict) and isinstance(request, dict)
    for label, value, allowed in (("profile", profile, PROFILE_FIELDS), ("observation", observation, OBSERVATION_FIELDS), ("request", request, REQUEST_FIELDS)):
        if set(value) - allowed:
            errors.append(f"{label}_unknown_fields")
    if profile.get("schema_version") != 1 or observation.get("schema_version") != 1 or request.get("schema_version") != 1:
        errors.append("schema_version_invalid")
    if profile.get("status") != "reviewed" or not isinstance(profile.get("profile_id"), str) or not profile["profile_id"].strip():
        errors.append("profile_not_reviewed")
    for field in IDENTITY:
        values = [value.get(field) for value in (profile, observation, request)]
        if any(not isinstance(v, str) or not v.strip() for v in values):
            errors.append(f"{field}_missing")
        elif len(set(values)) != 1:
            errors.append(f"{field}_mismatch")
    if profile.get("platform") not in PLATFORMS:
        errors.append("platform_unsupported")
    caps = profile.get("capabilities")
    seen = observation.get("capabilities")
    needed = request.get("required_capabilities")
    if (not isinstance(caps, list) or not isinstance(seen, list) or not isinstance(needed, list)
            or any(not isinstance(x, str) or not x.strip() for group in (caps, seen, needed) for x in group)):
        errors.append("capabilities_invalid")
    else:
        if len(caps) != len(set(caps)) or len(seen) != len(set(seen)) or len(needed) != len(set(needed)):
            errors.append("capabilities_duplicate")
        if set(needed) - set(caps):
            errors.append("profile_capability_missing")
        if set(needed) - set(seen):
            errors.append("observed_capability_missing")
    if request.get("operation") not in {"read", "write"}:
        errors.append("operation_invalid")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        errors.append("clock_without_timezone")
    reviewed = _date(profile.get("reviewed_at"))
    expires = _date(profile.get("expires_at"))
    observed = _date(observation.get("observed_at"))
    if not reviewed or not expires or reviewed >= expires or expires <= current:
        errors.append("profile_expired_or_unreviewed")
    if not observed or (current - observed).total_seconds() > 120 or (observed - current).total_seconds() > 30:
        errors.append("observation_stale")
    if reviewed and observed and observed < reviewed:
        errors.append("observation_predates_review")
    return {
        "schema_version": 1, "status": "blocked" if errors else "passed",
        "error_codes": sorted(set(errors)),
        "profile_id": profile.get("profile_id"),
        "observed_at": observation.get("observed_at"),
        "profile_expires_at": profile.get("expires_at"),
        "profile_sha256": hashlib.sha256(json.dumps(profile, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "write_authorized": False,
        "scope": "identity_and_capability_only",
    }
