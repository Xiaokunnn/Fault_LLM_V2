"""Prompt/output contract for the next Chinese-canonical extraction run.

The historical ``bailian_qwen_pilot.mjs`` remains a frozen four-page pilot.
This module defines the Stage-02 contract that the 24-page targeted run must
use, regardless of the eventual API transport implementation.
"""

from __future__ import annotations

import json
from typing import Mapping

from research_point_1_graph_evidence.stage03_schema_validation.chinese_canonicalizer import (
    contains_han,
)


NODE_TYPES = (
    "Equipment",
    "Component",
    "FaultMode",
    "FailureMechanism",
    "Symptom",
    "SignalFeature",
    "Cause",
    "OperatingCondition",
    "InspectionMethod",
    "InspectionAction",
    "MaintenanceAction",
    "Standard",
    "Risk",
)

RELATIONS_V1 = (
    "contains",
    "located_in",
    "occurs_at",
    "causes",
    "indicates",
    "manifests_as",
    "evolves_to",
    "diagnosed_by",
    "inspected_by",
    "mitigated_by",
    "maintained_by",
    "operates_under",
    "increases_risk_of",
    "specified_by",
)

RELATIONS = RELATIONS_V1 + ("prevented_by",)

EVIDENCE_ROLES = (
    "structural_context",
    "symptom",
    "cause_or_mechanism",
    "inspection",
    "maintenance",
    "operating_condition",
    "risk",
    "standard",
)

EVIDENCE_MODES = (
    "E1_contiguous_text",
    "E2_table_cells",
)

SYSTEM_PROMPT_ZH_V1 = f"""你从单个船舶机舱泵系技术文档页面中抽取候选三元组。

只返回JSON对象，不要输出解释。每条候选必须包含：
- head_surface、tail_surface：逐字复制页面原文中的实体表述，不得翻译；
- head_canonical_zh、tail_canonical_zh：面向中文图谱的简洁中文规范名；
- head_type、tail_type：只能使用 {", ".join(NODE_TYPES)}；
- relation：只能使用稳定机器码 {", ".join(RELATIONS_V1)}；
- evidence_text：逐字复制一个连续原文跨度；不得翻译、改写、拼接或使用省略号；
- evidence_mode：E1_contiguous_text 或 E2_table_cells；
- evidence_unit_ids：E2时填写解析器提供的单元格ID，E1时为空数组；
- evidence_role：只能使用 {", ".join(EVIDENCE_ROLES)}；
- fault_class_ids：原文明确支持时才填写；
- model_confidence、head_translation_confidence、tail_translation_confidence：0到1。

强制规则：
1. 原文实体和evidence_text用于证据核验，中文规范名绝不能替代原文。
2. 中文规范名必须是中文术语；型号、NPSH、API、ISO、单位等受保护标记必须保留。
3. 关系与实体类型保留英文机器码，中文显示名由本地词典确定。
4. 只抽取本页明确陈述的关系，不补充常识，不跨页推断。
5. 模型给出的中文规范名只是候选；是否进入中文图谱由本地术语词典或独立复核决定。
6. 页面无合格事实时返回空triples数组。
7. causes关系必须保持“原因/机理/工况 -> causes -> 症状/故障/风险”方向，禁止输出“症状 -> causes -> 原因”。例如表格中FAULT为低流量、CAUSE为管路堵塞时，必须输出“管路堵塞 -> causes -> 低流量”。
8. E2表格证据必须在evidence_unit_ids中同时列出包含head_surface和tail_surface的全部单元格ID；合并单元格可与同一row_group_id的原因或措施单元格配对。不得只引用一端的单元格。
9. 优先且原则上只抽取DOCUMENT_METADATA中的target_evidence_roles与target_fault_classes；未被定向请求的结构组成关系不要输出。

输出结构：
{{
  "triples": [
    {{
      "head_surface": "原文实体",
      "head_canonical_zh": "中文规范名",
      "head_type": "类型码",
      "relation": "关系码",
      "tail_surface": "原文实体",
      "tail_canonical_zh": "中文规范名",
      "tail_type": "类型码",
      "evidence_text": "连续原文",
      "evidence_mode": "E1_contiguous_text",
      "evidence_unit_ids": [],
      "evidence_role": "cause_or_mechanism",
      "fault_class_ids": [],
      "model_confidence": 0.0,
      "head_translation_confidence": 0.0,
      "tail_translation_confidence": 0.0
    }}
  ],
  "warnings": []
}}"""


SYSTEM_PROMPT_ZH_V2_GAP_REPAIR = f"""你从单个船舶机舱泵系技术文档页面中抽取缺口修复候选三元组。

只返回JSON对象，不要输出解释。每条候选必须包含：
- head_surface、tail_surface：逐字复制页面原文中的实体表述，不得翻译；
- head_canonical_zh、tail_canonical_zh：面向中文图谱的简洁中文规范名；
- head_type、tail_type：只能使用 {", ".join(NODE_TYPES)}；
- relation：只能使用稳定机器码 {", ".join(RELATIONS)}；
- evidence_text：逐字复制一个连续原文跨度；不得翻译、改写、拼接或使用省略号；
- evidence_mode：E1_contiguous_text 或 E2_table_cells；
- evidence_unit_ids：E2时填写解析器提供的单元格ID，E1时为空数组；
- evidence_role：只能使用 {", ".join(EVIDENCE_ROLES)}；
- fault_class_ids：只能填写DOCUMENT_METADATA中定向请求且被原文明确支持的类别；
- model_confidence、head_translation_confidence、tail_translation_confidence：0到1。

本轮目标是补齐证据角色。必须逐项扫描页面，按以下优先级抽取，不得在抽到原因关系后停止：
1. inspection：检查方法、测量方法、诊断方法、核查动作；
2. maintenance：维护措施、修理措施、纠正措施、预防措施；
3. symptom：故障表现、报警、泄漏、噪声、振动、温升、性能下降等；
4. cause_or_mechanism：只在DOCUMENT_METADATA明确要求时抽取。

关系与方向规则：
- 故障/机理/症状 -> diagnosed_by 或 inspected_by -> 检查方法/检查动作；
- 故障/原因/风险 -> mitigated_by -> 纠正或维修动作；
- 故障/机理/不期望工况 -> prevented_by -> 明确的预防动作；
- 设备/部件 -> maintained_by -> 维护动作；
- 故障/机理 -> manifests_as -> 症状，或症状/信号 -> indicates -> 故障/机理；
- 原因/机理/工况 -> causes -> 故障/症状。

prevented_by只用于原文同时明确写出“不期望事件”和“防止/避免该事件的动作”时。
它表示预防，不得改写成causes。保护阀、护套管等物理部件不是MaintenanceAction，
不得为了通过类型校验把物理部件伪装成维护动作。

表格规则：
- 对FAULT/PROBLEM/SYMPTOM—CAUSE—REMEDY/CORRECTION表，不能只抽CAUSE；
- 同时抽取明确的故障表现、检查/纠正/维护/预防关系；
- E2必须引用同时覆盖两端实体的解析器单元格ID；
- 两端必须位于同一row_id，或位于同一已验证row_group_id；
- 禁止拼接相邻行、相邻项目或不同表格；
- 如果表格结构不足以确认方向，放弃该条，不得猜测。

证据硬规则：
1. head_surface、tail_surface必须都出现在evidence_text或所列E2单元格中；
2. E1必须是页面中的一个连续跨度；禁止把标题和远处项目拼接；
3. 指令只暗示某故障但没有在同一证据跨度明确写出该故障时，不抽取该关系；
4. 保留否定、条件和适用范围，不把“可能”夸大为确定因果；
5. 只抽取本页明确陈述的关系，不补充工程常识，不跨页推断；
6. 中文规范名只是候选，不能代替外文原文参与证据核验；
7. 页面无合格事实时返回空triples数组。

输出结构：
{{
  "triples": [
    {{
      "head_surface": "原文实体",
      "head_canonical_zh": "中文规范名",
      "head_type": "类型码",
      "relation": "关系码",
      "tail_surface": "原文实体",
      "tail_canonical_zh": "中文规范名",
      "tail_type": "类型码",
      "evidence_text": "连续原文",
      "evidence_mode": "E1_contiguous_text",
      "evidence_unit_ids": [],
      "evidence_role": "inspection",
      "fault_class_ids": [],
      "model_confidence": 0.0,
      "head_translation_confidence": 0.0,
      "tail_translation_confidence": 0.0
    }}
  ],
  "warnings": []
}}"""

SYSTEM_PROMPT_ZH_V3_SYMPTOM_REPAIR = (
    SYSTEM_PROMPT_ZH_V2_GAP_REPAIR
    + """

本轮仅修复故障表现的实体类型和关系。追加约束：
1. 泄漏量、滴漏、小股流、蒸汽泄漏、噪声、振动、温升和性能下降等可观察表现标为Symptom。
2. Component不能作为manifests_as的头实体。若原文直接描述某部件“泄漏”，应从原文中选择可观察故障状态作为FaultMode头实体，例如“initial leakage”或“shaft seal leaks”；不得凭空加入原文没有的failure。
3. manifests_as必须保持“FaultMode或FailureMechanism -> Symptom”方向，两端surface都必须逐字出现在同一连续证据跨度中。
4. 优先抽取DOCUMENT_METADATA要求的机械轴封症状；不要重复抽取普通维护、结构和原因关系。
"""
)

SYSTEM_PROMPT_ZH_V4_FULL_CORPUS = (
    SYSTEM_PROMPT_ZH_V2_GAP_REPAIR
    .replace(
        "缺口修复候选三元组",
        "全量知识图谱候选三元组",
        1,
    )
    .replace(
        "本轮目标是补齐证据角色。必须逐项扫描页面，按以下优先级抽取，不得在抽到原因关系后停止：",
        "本轮目标是完整扫描当前页面中与船舶机舱泵系有关的明确事实。"
        "必须逐项扫描页面，覆盖下列证据角色，不得在抽到一种关系后停止：",
        1,
    )
)


def system_prompt_for_version(prompt_version: str) -> str:
    if prompt_version == "marine_pump_full_corpus_prompt_v4":
        return SYSTEM_PROMPT_ZH_V4_FULL_CORPUS
    if prompt_version == "marine_pump_symptom_role_repair_prompt_v3":
        return SYSTEM_PROMPT_ZH_V3_SYMPTOM_REPAIR
    if prompt_version == "marine_pump_gap_role_repair_prompt_v2":
        return SYSTEM_PROMPT_ZH_V2_GAP_REPAIR
    if prompt_version == "marine_pump_targeted_zh_prompt_v1":
        return SYSTEM_PROMPT_ZH_V1
    raise ValueError(f"Unknown prompt version: {prompt_version}")


def build_user_prompt(page: Mapping[str, object]) -> str:
    metadata = {
        "doc_id": page.get("doc_id"),
        "pdf_page_number": page.get("pdf_page_number"),
        "printed_page": page.get("printed_page"),
        "source_language": page.get("source_language"),
        "publisher": page.get("publisher"),
        "source_url": page.get("source_url"),
        "pump_type": page.get("pump_type"),
        "service": page.get("service"),
        "applicability_scope": page.get("applicability_scope"),
        "target_fault_classes": page.get("target_fault_classes", []),
        "target_evidence_roles": page.get("target_evidence_roles", []),
        "scope_note": page.get("scope_note"),
    }
    tables = page.get("tables", [])
    return (
        "DOCUMENT_METADATA\n"
        + json.dumps(metadata, ensure_ascii=False, indent=2)
        + "\n\nPARSED_TABLES\n"
        + json.dumps(tables, ensure_ascii=False)
        + "\n\nPAGE_TEXT_BEGIN\n"
        + str(page.get("page_text", ""))
        + "\nPAGE_TEXT_END"
    )


def normalize_model_candidate(
    model_candidate: Mapping[str, object],
    *,
    page: Mapping[str, object],
) -> dict[str, object]:
    """Normalize a model proposal without treating translation as evidence."""

    head_surface = str(model_candidate.get("head_surface", "")).strip()
    tail_surface = str(model_candidate.get("tail_surface", "")).strip()
    head_zh = str(model_candidate.get("head_canonical_zh", "")).strip()
    tail_zh = str(model_candidate.get("tail_canonical_zh", "")).strip()
    head_type = str(model_candidate.get("head_type", "")).strip()
    tail_type = str(model_candidate.get("tail_type", "")).strip()
    relation = str(model_candidate.get("relation", "")).strip()
    evidence_text = str(model_candidate.get("evidence_text", "")).strip()
    missing = [
        name
        for name, value in (
            ("head_surface", head_surface),
            ("tail_surface", tail_surface),
            ("head_canonical_zh", head_zh),
            ("tail_canonical_zh", tail_zh),
            ("head_type", head_type),
            ("tail_type", tail_type),
            ("relation", relation),
            ("evidence_text", evidence_text),
        )
        if not value
    ]
    if missing:
        raise ValueError("Missing model candidate fields: " + ", ".join(missing))
    if head_type not in NODE_TYPES or tail_type not in NODE_TYPES:
        raise ValueError("Unknown entity type in model candidate")
    if relation not in RELATIONS:
        raise ValueError(f"Unknown relation in model candidate: {relation}")
    if not contains_han(head_zh) or not contains_han(tail_zh):
        raise ValueError("Chinese canonical labels must contain Han characters")
    evidence_mode = str(
        model_candidate.get("evidence_mode", "E1_contiguous_text")
    ).strip()
    if evidence_mode not in EVIDENCE_MODES:
        raise ValueError(f"Unknown evidence mode: {evidence_mode}")
    evidence_unit_ids = [
        str(value).strip()
        for value in list(model_candidate.get("evidence_unit_ids", []) or [])
        if str(value).strip()
    ]
    if evidence_mode == "E1_contiguous_text" and evidence_unit_ids:
        raise ValueError("E1 evidence must not include table cell IDs")
    if evidence_mode == "E2_table_cells" and not evidence_unit_ids:
        raise ValueError("E2 evidence requires parser-generated table cell IDs")
    evidence_role = str(model_candidate.get("evidence_role", "")).strip()
    if evidence_role not in EVIDENCE_ROLES:
        raise ValueError(f"Unknown evidence role: {evidence_role}")

    return {
        "head": head_surface,
        "head_surface": head_surface,
        "head_canonical_zh": head_zh,
        "head_type": head_type,
        "head_translation_status": "needs_review",
        "relation": relation,
        "tail": tail_surface,
        "tail_surface": tail_surface,
        "tail_canonical_zh": tail_zh,
        "tail_type": tail_type,
        "tail_translation_status": "needs_review",
        "evidence_text": evidence_text,
        "evidence_mode": evidence_mode,
        "evidence_unit_ids": evidence_unit_ids,
        "evidence_role": evidence_role,
        "fault_class_ids": list(
            model_candidate.get("fault_class_ids", []) or []
        ),
        "model_confidence": float(
            model_candidate.get("model_confidence", 0.0) or 0.0
        ),
        "head_translation_confidence": float(
            model_candidate.get("head_translation_confidence", 0.0) or 0.0
        ),
        "tail_translation_confidence": float(
            model_candidate.get("tail_translation_confidence", 0.0) or 0.0
        ),
        "doc_id": page.get("doc_id"),
        "pdf_page_number": page.get("pdf_page_number"),
        "document_split": page.get("document_split"),
        "source_language": page.get("source_language"),
        "source_family_id": page.get("source_family_id"),
        "source_url": page.get("source_url"),
        "source_tier": page.get("source_tier"),
        "publisher": page.get("publisher"),
        "document_sha256": page.get("document_sha256"),
        "page_text_sha256": page.get("page_text_sha256"),
        "pump_type": page.get("pump_type"),
        "service": page.get("service"),
        "applicability_scope": page.get("applicability_scope"),
        "inferred_edge": False,
    }
