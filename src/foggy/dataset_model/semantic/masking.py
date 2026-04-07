"""Column governance — masking execution (v1.2).

Applies data masking to query result rows based on the ``masking`` rules
defined in :class:`FieldAccessDef`.

Supported mask types:

* ``full_mask``    — replace value with ``***``
* ``partial_mask`` — keep first char, mask the rest (``张**``)
* ``email_mask``   — ``z***@example.com``
* ``phone_mask``   — ``138****5678``
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from foggy.mcp_spi.semantic import FieldAccessDef

# ---------------------------------------------------------------------------
# Mask functions
# ---------------------------------------------------------------------------

_FULL_MASK = "***"


def _mask_full(value: Any) -> str:
    """Replace value entirely with ``***``."""
    return _FULL_MASK


def _mask_partial(value: Any) -> str:
    """Keep first character, mask the rest.

    ``"张三丰"`` → ``"张**"``
    ``"Alice"`` → ``"A****"``
    ``""`` or None → ``"***"``
    """
    s = str(value) if value is not None else ""
    if len(s) <= 1:
        return _FULL_MASK
    return s[0] + "*" * (len(s) - 1)


def _mask_email(value: Any) -> str:
    """Mask email keeping first char of local part and domain.

    ``"zhang@example.com"`` → ``"z***@example.com"``
    Non-email values get full_mask.
    """
    s = str(value) if value is not None else ""
    if "@" not in s:
        return _FULL_MASK
    local, domain = s.rsplit("@", 1)
    if not local:
        return _FULL_MASK
    return local[0] + "***@" + domain


def _mask_phone(value: Any) -> str:
    """Mask phone keeping first 3 and last 4 digits.

    ``"13812345678"`` → ``"138****5678"``
    Shorter values get partial_mask treatment.
    """
    s = str(value) if value is not None else ""
    # Extract digits only for pattern matching
    digits = re.sub(r"[^\d]", "", s)
    if len(digits) >= 7:
        return digits[:3] + "****" + digits[-4:]
    # Fallback to partial mask for short numbers
    return _mask_partial(s)


_MASK_FUNCS = {
    "full_mask": _mask_full,
    "partial_mask": _mask_partial,
    "email_mask": _mask_email,
    "phone_mask": _mask_phone,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def apply_masking(
    items: List[Dict[str, Any]],
    field_access: Optional[FieldAccessDef],
    display_to_qm: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Apply masking rules to query result rows **in-place** and return them.

    Parameters
    ----------
    items
        Result rows.  Keys are **display names** (SQL aliases).
    field_access
        Column governance.  ``masking`` maps QM field names → mask types.
    display_to_qm
        Mapping from display-name key → QM field name.  Used to translate
        row keys before looking up masking rules.  ``None`` means keys are
        matched directly (unit-test / legacy compat).

    If ``field_access`` is ``None`` or ``masking`` is empty, rows are returned
    unchanged (v1.1 compat).

    Unknown mask types are silently treated as ``full_mask`` to avoid data
    leakage.
    """
    if not field_access or not field_access.masking:
        return items
    if not items:
        return items

    # Pre-resolve: QM field name → mask function
    qm_resolved: Dict[str, Any] = {}
    for field_name, mask_type in field_access.masking.items():
        qm_resolved[field_name] = _MASK_FUNCS.get(mask_type, _mask_full)

    # Build reverse map: QM field name → display name(s) in row keys
    qm_to_display: Dict[str, str] = {}
    if display_to_qm:
        for disp, qm in display_to_qm.items():
            qm_to_display[qm] = disp

    for row in items:
        for qm_name, mask_fn in qm_resolved.items():
            # Try display-name lookup first, fall back to direct key match
            key = qm_to_display.get(qm_name, qm_name)
            if key in row:
                row[key] = mask_fn(row[key])

    return items
