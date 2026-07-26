"""Conservative relation-entailment validation.

This standard-library validator does not pretend to solve unrestricted natural
language inference.  It accepts direct relation cues in E1 evidence or a
relation explicitly established by a validated E2 table schema.  Everything
else remains undetermined and cannot automatically enter the Silver layer.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Mapping, Sequence
import unicodedata

from .evidence_span_validator import E1, E2, E3


DEFAULT_RELATION_CUES: dict[str, tuple[str, ...]] = {
    "causes": (
        r"\bcaus(?:e|es|ed|ing)\b",
        r"\bdue to\b",
        r"\bbecause of\b",
        r"\bresults? in\b",
        r"\bleads? to\b",
        r"\bproduces?\b",
        r"(?:导致|引起|造成|致使)",
        r"(?:由于|因为|因而|因此)",
    ),
    "indicates": (
        r"\bindicat(?:e|es|ed|ing)\b",
        r"\bsign of\b",
        r"\bevidence of\b",
        r"\bsuggests?\b",
        r"(?:表明|指示|说明|提示|征兆)",
    ),
    "manifests_as": (
        r"\bmanifests? as\b",
        r"\bappears? as\b",
        r"\bcharacteri[sz]ed by\b",
        r"\bsymptoms?\b",
        r"(?:表现为|呈现为|症状为|特征为|特征是)",
    ),
    "evolves_to": (
        r"\bevolves? to\b",
        r"\bdevelops? into\b",
        r"\bprogresses? to\b",
        r"(?:演变为|演化为|发展为|恶化为)",
    ),
    "diagnosed_by": (
        r"\bdiagnos(?:e|es|ed|ing|is)\b",
        r"\bdetect(?:s|ed|ing|ion)?\b",
        r"\bmeasure(?:s|d|ment|ments|ing)?\b",
        r"\banalys(?:is|e|es|ed|ing)\b",
        r"\bmonitor(?:s|ed|ing)?\b",
        r"(?:诊断|检测|测量|分析|监测)",
    ),
    "inspected_by": (
        r"\binspect(?:s|ed|ing|ion)?\b",
        r"\bcheck(?:s|ed|ing)?\b",
        r"\btest(?:s|ed|ing)?\b",
        r"\bexamin(?:e|es|ed|ing|ation)\b",
        r"(?:检查|检验|测试|查看|确认)",
    ),
    "mitigated_by": (
        r"\bmitigat(?:e|es|ed|ing|ion)\b",
        r"\brepair(?:s|ed|ing)?\b",
        r"\breplac(?:e|es|ed|ing)\b",
        r"\bcorrect(?:s|ed|ing|ion)?\b",
        r"\bremed(?:y|ies|ied)\b",
        r"\bshut down\b",
        r"(?:缓解|修复|更换|纠正|处理|消除|停机)",
    ),
    "prevented_by": (
        r"\bprevent(?:s|ed|ing|ion)?\b",
        r"\bavoid(?:s|ed|ing|ance)?\b",
        r"\bprotect(?:s|ed|ing|ion)?\b.+\bfrom\b",
        r"\b(?:must|should|shall)\s+not\b",
        r"\bnever\b",
        r"(?:防止|预防|避免|严禁|不得|禁止)",
    ),
    "maintained_by": (
        r"\bmaintain(?:s|ed|ing|maintenance)?\b",
        r"\blubricat(?:e|es|ed|ing|ion)\b",
        r"\bservice(?:s|d|ing)?\b",
        r"\bclean(?:s|ed|ing)?\b",
        r"\breplac(?:e|es|ed|ing)\b",
        r"(?:维护|维修|保养|润滑|清洁|清理|更换)",
    ),
    "contains": (
        r"\bcontains?\b",
        r"\bcomprises?\b",
        r"\bconsists? of\b",
        r"(?:包含|包括|由.{0,30}组成)",
    ),
    "located_in": (
        r"\blocated in\b",
        r"\binstalled in\b",
        r"\bmounted in\b",
        r"(?:位于|安装在|装在)",
    ),
    "occurs_at": (
        r"\boccurs? (?:at|in)\b",
        r"\bfailure (?:at|in)\b",
        r"\bfault (?:at|in)\b",
        r"(?:发生于|发生在|出现在)",
    ),
    "operates_under": (
        r"\boperat(?:e|es|ed|ing)\b",
        r"\bunder\b",
        r"(?:运行于|工作于|在.{0,30}(?:工况|条件)下)",
    ),
    "increases_risk_of": (
        r"\bincreases? (?:the )?risk of\b",
        r"\brisk of\b",
        r"\bmay lead to\b",
        r"(?:增加.{0,20}风险|可能导致|存在.{0,20}风险)",
    ),
    "specified_by": (
        r"\bspecified by\b",
        r"\bin accordance with\b",
        r"\bshall comply with\b",
        r"(?:由.{0,30}规定|依据|按照|符合)",
    ),
}


@dataclass(frozen=True)
class RelationEntailmentValidation:
    valid: bool
    status: str
    matched_cues: tuple[str, ...]
    silver_eligible: bool
    hard_veto_reasons: tuple[str, ...] = ()
    silver_veto_reasons: tuple[str, ...] = ()
    review_reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _normalized(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def validate_relation_entailment(
    *,
    relation: str,
    evidence_text: str,
    head_surface: str,
    tail_surface: str,
    evidence_level: str,
    structured_relation: str | None = None,
    relation_cues: Mapping[str, Sequence[str]] | None = None,
) -> RelationEntailmentValidation:
    evidence_normalized = _normalized(evidence_text)
    missing: list[str] = []
    if _normalized(head_surface) not in evidence_normalized:
        missing.append("head_surface_not_in_relation_evidence")
    if _normalized(tail_surface) not in evidence_normalized:
        missing.append("tail_surface_not_in_relation_evidence")
    if missing:
        return RelationEntailmentValidation(
            valid=False,
            status="not_entailed",
            matched_cues=(),
            silver_eligible=False,
            hard_veto_reasons=tuple(missing),
        )

    if evidence_level == E3:
        return RelationEntailmentValidation(
            valid=False,
            status="undetermined",
            matched_cues=(),
            silver_eligible=False,
            silver_veto_reasons=("e3_relation_entailment_not_automatic",),
            review_reasons=("relation_entailment_requires_review",),
        )

    if evidence_level == E2:
        if structured_relation == relation:
            return RelationEntailmentValidation(
                valid=True,
                status="entailed",
                matched_cues=("verified_table_structure",),
                silver_eligible=True,
            )
        if structured_relation:
            return RelationEntailmentValidation(
                valid=False,
                status="not_entailed",
                matched_cues=(),
                silver_eligible=False,
                hard_veto_reasons=("table_relation_mismatch",),
            )
        return RelationEntailmentValidation(
            valid=False,
            status="undetermined",
            matched_cues=(),
            silver_eligible=False,
            silver_veto_reasons=("table_relation_not_declared",),
            review_reasons=("table_relation_requires_review",),
        )

    if evidence_level != E1:
        return RelationEntailmentValidation(
            valid=False,
            status="not_entailed",
            matched_cues=(),
            silver_eligible=False,
            hard_veto_reasons=("unknown_evidence_level",),
        )

    cue_map = relation_cues or DEFAULT_RELATION_CUES
    patterns = tuple(str(item) for item in cue_map.get(relation, ()))
    matched = tuple(
        pattern
        for pattern in patterns
        if re.search(pattern, evidence_text, flags=re.IGNORECASE)
    )
    if matched:
        return RelationEntailmentValidation(
            valid=True,
            status="entailed",
            matched_cues=matched,
            silver_eligible=True,
        )
    return RelationEntailmentValidation(
        valid=False,
        status="undetermined",
        matched_cues=(),
        silver_eligible=False,
        silver_veto_reasons=("relation_cue_not_verified",),
        review_reasons=("relation_entailment_requires_review",),
    )
