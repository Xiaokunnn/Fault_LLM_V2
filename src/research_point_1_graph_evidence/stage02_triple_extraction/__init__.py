"""Stage-02 extraction contracts and transport adapters."""

from .chinese_extraction_contract import (
    EVIDENCE_ROLES,
    EVIDENCE_MODES,
    NODE_TYPES,
    RELATIONS,
    SYSTEM_PROMPT_ZH_V1,
    SYSTEM_PROMPT_ZH_V2_GAP_REPAIR,
    build_user_prompt,
    normalize_model_candidate,
    system_prompt_for_version,
)

__all__ = [
    "EVIDENCE_ROLES",
    "EVIDENCE_MODES",
    "NODE_TYPES",
    "RELATIONS",
    "SYSTEM_PROMPT_ZH_V1",
    "SYSTEM_PROMPT_ZH_V2_GAP_REPAIR",
    "build_user_prompt",
    "normalize_model_candidate",
    "system_prompt_for_version",
]
