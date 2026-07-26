"""Unit tests for the strict Stage 03 marine-pump validation modules."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from research_point_1_graph_evidence.stage03_schema_validation import (  # noqa: E402
    CoverageThresholds,
    build_coverage_report,
    decide_confidence,
    deduplicate_triples,
    enrich_stable_ids,
    load_fault_ontology,
    load_provenance_schema,
    map_fault_classes,
    missing_required_fields,
    normalize_relation_direction,
    stable_claim_id,
    stable_entity_id,
    validate_evidence_span,
    validate_candidate,
    validate_relation_entailment,
    validate_relation_type,
    validate_table_alignment,
)


class EvidenceSpanTests(unittest.TestCase):
    def test_exact_e1_records_entity_offsets(self) -> None:
        page = "Blocked suction pipe causes low pump capacity."
        result = validate_evidence_span(
            page_text=page,
            evidence_text=page,
            head_surface="Blocked suction pipe",
            tail_surface="low pump capacity",
        )
        self.assertTrue(result.valid)
        self.assertEqual(result.evidence_level, "E1")
        self.assertEqual(result.match_method, "exact")
        self.assertTrue(result.silver_eligible)
        self.assertEqual(result.head_span.start, 0)
        self.assertEqual(
            page[result.tail_span.start : result.tail_span.end],
            "low pump capacity",
        )

    def test_whitespace_normalized_e1_returns_source_text(self) -> None:
        page = "Blocked suction pipe\n    causes low pump capacity."
        result = validate_evidence_span(
            page_text=page,
            evidence_text="Blocked suction pipe causes low pump capacity.",
            head_surface="Blocked suction pipe",
            tail_surface="low pump capacity",
        )
        self.assertTrue(result.valid)
        self.assertEqual(result.match_method, "whitespace_normalized")
        self.assertEqual(result.evidence_text, page)

    def test_direct_quote_without_tail_anchor_is_invalid(self) -> None:
        page = "Blocked suction pipe. Elsewhere: low pump capacity."
        result = validate_evidence_span(
            page_text=page,
            evidence_text="Blocked suction pipe.",
            head_surface="Blocked suction pipe",
            tail_surface="low pump capacity",
        )
        self.assertFalse(result.valid)
        self.assertIn("tail_surface_not_in_evidence", result.hard_veto_reasons)

    def test_reconstructed_context_is_e3_and_never_automatic_silver(self) -> None:
        page = "Blocked suction pipe\nnoise between cells\nlow pump capacity"
        result = validate_evidence_span(
            page_text=page,
            evidence_text="a model paraphrase not found in the page",
            head_surface="Blocked suction pipe",
            tail_surface="low pump capacity",
        )
        self.assertTrue(result.valid)
        self.assertEqual(result.evidence_level, "E3")
        self.assertFalse(result.silver_eligible)
        self.assertIn("evidence_level_e3_not_silver", result.silver_veto_reasons)

    def test_legacy_reconstructed_span_cannot_be_relabelled_as_e1(self) -> None:
        page = "Blocked suction pipe causes low pump capacity."
        result = validate_candidate(
            {
                "head": "Blocked suction pipe",
                "head_type": "Cause",
                "relation": "causes",
                "tail": "low pump capacity",
                "tail_type": "Symptom",
                "evidence_text": page,
                "model_confidence": 0.99,
                "source_tier": "A",
                "document_split": "build_train",
                "validation_votes": {
                    "evidence_match_method": "head_tail_context_reconstructed"
                },
            },
            page_text=page,
            project_root=PROJECT_ROOT,
        )
        self.assertEqual(result["evidence_level"], "E3")
        self.assertEqual(result["decision"], "candidate_needs_review")
        self.assertIn(
            "legacy_reconstructed_evidence_cannot_be_promoted",
            result["evidence_validation"]["silver_veto_reasons"],
        )

    def test_ellipsis_is_rejected(self) -> None:
        result = validate_evidence_span(
            page_text="Blocked suction pipe causes low capacity.",
            evidence_text="Blocked suction pipe ... low capacity",
            head_surface="Blocked suction pipe",
            tail_surface="low capacity",
        )
        self.assertFalse(result.valid)
        self.assertIn("evidence_contains_ellipsis", result.hard_veto_reasons)

    def test_unicode_ellipsis_is_rejected(self) -> None:
        result = validate_evidence_span(
            page_text="吸入管堵塞导致流量过低。",
            evidence_text="吸入管堵塞…流量过低",
            head_surface="吸入管堵塞",
            tail_surface="流量过低",
        )
        self.assertFalse(result.valid)
        self.assertIn("evidence_contains_ellipsis", result.hard_veto_reasons)


class TableAlignmentTests(unittest.TestCase):
    def _unit(
        self,
        page: str,
        text: str,
        *,
        row: str,
        column: str,
        group: str | None = None,
    ) -> dict[str, object]:
        start = page.index(text)
        return {
            "table_id": "T1",
            "row_id": row,
            "row_group_id": group,
            "column_name": column,
            "text": text,
            "start": start,
            "end": start + len(text),
        }

    def test_same_visual_row_is_valid_e2(self) -> None:
        page = "Low capacity       Blocked suction pipe"
        units = [
            self._unit(page, "Low capacity", row="R1", column="Symptom"),
            self._unit(page, "Blocked suction pipe", row="R1", column="Cause"),
        ]
        result = validate_table_alignment(
            page_text=page,
            evidence_units=units,
            head_surface="Blocked suction pipe",
            tail_surface="Low capacity",
            visual_layout_checked=True,
        )
        self.assertTrue(result.valid)
        self.assertEqual(result.evidence_level, "E2")
        self.assertEqual(result.alignment_method, "same_visual_row")

    def test_bbox_located_cells_do_not_require_page_text_serialization(self) -> None:
        page = "two-column page text is interleaved"
        units = [
            {
                "table_id": "T1",
                "row_id": "R1",
                "row_group_id": "R1",
                "column_name": "CAUSE",
                "text": "Blocked suction pipe",
                "start": -1,
                "end": -1,
                "bbox": [10, 10, 100, 30],
            },
            {
                "table_id": "T1",
                "row_id": "R1",
                "row_group_id": "R1",
                "column_name": "FAULT",
                "text": "Low capacity",
                "start": -1,
                "end": -1,
                "bbox": [110, 10, 200, 30],
            },
        ]
        result = validate_table_alignment(
            page_text=page,
            evidence_units=units,
            head_surface="Blocked suction pipe",
            tail_surface="Low capacity",
            visual_layout_checked=True,
        )
        self.assertTrue(result.valid)
        self.assertIn("table_cells_located_by_bbox", result.review_reasons)

    def test_verified_merged_row_group_can_span_rows(self) -> None:
        page = "Low capacity\nBlocked suction pipe"
        units = [
            self._unit(
                page, "Low capacity", row="R1", group="G1", column="Symptom"
            ),
            self._unit(
                page,
                "Blocked suction pipe",
                row="R2",
                group="G1",
                column="Cause",
            ),
        ]
        result = validate_table_alignment(
            page_text=page,
            evidence_units=units,
            head_surface="Blocked suction pipe",
            tail_surface="Low capacity",
            visual_layout_checked=True,
        )
        self.assertTrue(result.valid)
        self.assertEqual(result.alignment_method, "verified_merged_row_group")

    def test_unverified_cross_row_evidence_is_rejected(self) -> None:
        page = "Low capacity\nBlocked suction pipe"
        units = [
            self._unit(page, "Low capacity", row="R1", column="Symptom"),
            self._unit(page, "Blocked suction pipe", row="R2", column="Cause"),
        ]
        result = validate_table_alignment(
            page_text=page,
            evidence_units=units,
            head_surface="Blocked suction pipe",
            tail_surface="Low capacity",
            visual_layout_checked=True,
        )
        self.assertFalse(result.valid)
        self.assertIn("cross_row_table_evidence", result.hard_veto_reasons)


class RelationValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = load_provenance_schema(project_root=PROJECT_ROOT)

    def test_relation_type_is_separate_from_entailment(self) -> None:
        result = validate_relation_type(
            relation="causes",
            head_type="Cause",
            tail_type="Symptom",
            schema=self.schema,
        )
        self.assertTrue(result.valid)
        entailment = validate_relation_entailment(
            relation="causes",
            evidence_text="Blocked suction pipe and low pump capacity.",
            head_surface="Blocked suction pipe",
            tail_surface="low pump capacity",
            evidence_level="E1",
        )
        self.assertFalse(entailment.valid)
        self.assertEqual(entailment.status, "undetermined")

    def test_v2_required_fields_are_resolved_for_evidence_assertion(self) -> None:
        missing = missing_required_fields({}, self.schema)
        self.assertIn("assertion_id", missing)
        self.assertIn("claim_id", missing)
        self.assertNotIn("manifest", missing)

    def test_explicit_v1_schema_remains_supported(self) -> None:
        schema = load_provenance_schema(
            PROJECT_ROOT
            / "data"
            / "kg"
            / "marine_pump"
            / "schema"
            / "provenance_schema_v1.json"
        )
        result = validate_relation_type(
            relation="causes",
            head_type="Cause",
            tail_type="Symptom",
            schema=schema,
        )
        self.assertTrue(result.valid)

    def test_invalid_relation_type_pair_is_rejected(self) -> None:
        result = validate_relation_type(
            relation="causes",
            head_type="InspectionMethod",
            tail_type="Symptom",
            schema=self.schema,
        )
        self.assertFalse(result.valid)
        self.assertIn("head_type_not_allowed_for_relation", result.reasons)

    def test_causal_cue_entails_e1_relation(self) -> None:
        result = validate_relation_entailment(
            relation="causes",
            evidence_text="Blocked suction pipe causes low pump capacity.",
            head_surface="Blocked suction pipe",
            tail_surface="low pump capacity",
            evidence_level="E1",
        )
        self.assertTrue(result.valid)
        self.assertEqual(result.status, "entailed")

    def test_verified_table_relation_entails_e2(self) -> None:
        result = validate_relation_entailment(
            relation="causes",
            evidence_text="Blocked suction pipe | Low capacity",
            head_surface="Blocked suction pipe",
            tail_surface="Low capacity",
            evidence_level="E2",
            structured_relation="causes",
        )
        self.assertTrue(result.valid)
        self.assertIn("verified_table_structure", result.matched_cues)

    def test_direction_normalization_is_auditable(self) -> None:
        result = normalize_relation_direction(
            head="Low capacity",
            head_type="Symptom",
            relation="causes",
            tail="Blocked suction pipe",
            tail_type="Cause",
        )
        self.assertEqual(result.head, "Blocked suction pipe")
        self.assertEqual(result.tail, "Low capacity")
        self.assertEqual(result.actions, ("reoriented_cause_to_effect",))

    def test_relation_name_is_not_changed_from_node_type_alone(self) -> None:
        result = normalize_relation_direction(
            head="High vibration",
            head_type="Symptom",
            relation="indicates",
            tail="Repair bearing",
            tail_type="MaintenanceAction",
        )
        self.assertEqual(result.relation, "indicates")
        self.assertEqual(result.actions, ())

    def test_reverse_mitigation_is_canonicalized(self) -> None:
        result = normalize_relation_direction(
            head="Replace the seal",
            head_type="MaintenanceAction",
            relation="mitigated_by",
            tail="Seal failure",
            tail_type="FaultMode",
        )
        self.assertEqual(result.head, "Seal failure")
        self.assertEqual(result.tail, "Replace the seal")
        self.assertEqual(result.relation, "mitigated_by")
        self.assertIn("reoriented_mitigated_target_to_action", result.actions)

    def test_prevention_relation_v3_is_typed_and_directly_entailed(self) -> None:
        schema_v3 = load_provenance_schema(
            PROJECT_ROOT
            / "data"
            / "kg"
            / "marine_pump"
            / "schema"
            / "provenance_schema_v3.json"
        )
        relation_type = validate_relation_type(
            relation="prevented_by",
            head_type="FaultMode",
            tail_type="MaintenanceAction",
            schema=schema_v3,
        )
        self.assertTrue(relation_type.valid)
        entailment = validate_relation_entailment(
            relation="prevented_by",
            evidence_text=(
                "Dry running can be prevented by filling the pump before start."
            ),
            head_surface="Dry running",
            tail_surface="filling the pump before start",
            evidence_level="E1",
        )
        self.assertTrue(entailment.valid)

    def test_reverse_prevention_is_canonicalized(self) -> None:
        result = normalize_relation_direction(
            head="Fill the pump before starting",
            head_type="MaintenanceAction",
            relation="prevented_by",
            tail="Dry running",
            tail_type="FaultMode",
        )
        self.assertEqual(result.head, "Dry running")
        self.assertEqual(result.tail, "Fill the pump before starting")
        self.assertIn("reoriented_prevented_target_to_action", result.actions)

    def test_symptom_inspection_is_normalized_to_diagnosis(self) -> None:
        result = normalize_relation_direction(
            head="Low capacity",
            head_type="Symptom",
            relation="inspected_by",
            tail="Check discharge pressure",
            tail_type="InspectionAction",
        )
        self.assertEqual(result.relation, "diagnosed_by")
        self.assertIn(
            "normalized_symptom_inspection_to_diagnosis", result.actions
        )

    def test_fault_indicates_symptom_is_manifestation(self) -> None:
        result = normalize_relation_direction(
            head="Bearing failure",
            head_type="FaultMode",
            relation="indicates",
            tail="High vibration",
            tail_type="SignalFeature",
        )
        self.assertEqual(result.relation, "manifests_as")

    def test_contained_fault_is_normalized_to_occurs_at(self) -> None:
        result = normalize_relation_direction(
            head="Pump",
            head_type="Equipment",
            relation="contains",
            tail="Cavitation",
            tail_type="FaultMode",
        )
        self.assertEqual(result.head, "Cavitation")
        self.assertEqual(result.tail, "Pump")
        self.assertEqual(result.relation, "occurs_at")


class FaultClassMapperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.ontology_path = Path(self.temp_dir.name) / "ontology.json"
        self.ontology_path.write_text(
            json.dumps(
                {
                    "version": "test_fault_ontology_v1",
                    "fault_classes": [
                        {
                            "fault_id": "hydraulic_blockage",
                            "patterns": [
                                {
                                    "rule_id": "blocked_suction",
                                    "pattern": r"\bblocked suction pipe\b",
                                }
                            ],
                        },
                        {
                            "fault_id": "pump_motor_misalignment",
                            "patterns": [r"\bmisalign(?:ed|ment)?\b"],
                            "negative_patterns": [r"\balignment check\b"],
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_mapping_uses_claim_and_validated_evidence_only(self) -> None:
        ontology = load_fault_ontology(self.ontology_path)
        result = map_fault_classes(
            head_surface="Blocked suction pipe",
            tail_surface="Low capacity",
            evidence_text="Blocked suction pipe causes low capacity.",
            ontology=ontology,
            requested_fault_class_ids=[
                "hydraulic_blockage",
                "pump_motor_misalignment",
                "unknown_class",
            ],
        )
        self.assertEqual(result.fault_class_ids, ("hydraulic_blockage",))
        self.assertEqual(
            result.rejected_requested_ids, ("pump_motor_misalignment",)
        )
        self.assertEqual(result.invalid_requested_ids, ("unknown_class",))
        self.assertIn(
            "blocked_suction",
            result.matched_rule_ids["hydraulic_blockage"],
        )
        self.assertEqual(
            result.mapping_evidence["hydraulic_blockage"][0]["matched_text"],
            "Blocked suction pipe",
        )

    def test_negative_rule_prevents_alignment_false_positive(self) -> None:
        ontology = load_fault_ontology(self.ontology_path)
        result = map_fault_classes(
            head_surface="Alignment check",
            tail_surface="Pump",
            evidence_text="Perform the alignment check on the pump.",
            ontology=ontology,
        )
        self.assertNotIn("pump_motor_misalignment", result.fault_class_ids)

    def test_missing_ontology_has_actionable_error(self) -> None:
        missing = Path(self.temp_dir.name) / "missing.json"
        with self.assertRaisesRegex(
            FileNotFoundError, "fault_ontology_marine_pump_v1.json"
        ):
            load_fault_ontology(missing)

    def test_versioned_ontology_maps_direct_pipeline_preventive_action(self) -> None:
        ontology = load_fault_ontology(project_root=PROJECT_ROOT)
        result = map_fault_classes(
            head_surface="pipelines",
            tail_surface="Ensure that the pipelines are routed correctly",
            evidence_text="Ensure that the pipelines are routed correctly.",
            ontology=ontology,
            requested_fault_class_ids=["pipe_or_valve_integrity_failure"],
        )
        self.assertIn(
            "pipe_or_valve_integrity_failure",
            result.fault_class_ids,
        )
        self.assertIn(
            "pipe_integrity_preventive_action_en_reverse_v2",
            result.matched_rule_ids["pipe_or_valve_integrity_failure"],
        )

    def test_pipeline_action_in_other_table_cell_does_not_map_claim(self) -> None:
        ontology = load_fault_ontology(project_root=PROJECT_ROOT)
        result = map_fault_classes(
            head_surface="The pump does not prime",
            tail_surface="Change direction of rotation",
            evidence_text=(
                "The pump does not prime\n--- CELL ---\n"
                "Lower suction pipe/Tighten suction line\n"
                "Change direction of rotation"
            ),
            ontology=ontology,
        )
        self.assertNotIn(
            "pipe_or_valve_integrity_failure",
            result.fault_class_ids,
        )

    def test_check_valve_noun_is_not_mapped_as_integrity_action(self) -> None:
        ontology = load_fault_ontology(project_root=PROJECT_ROOT)
        result = map_fault_classes(
            head_surface="back flow",
            tail_surface="a check valve can be installed",
            evidence_text="A check valve can be installed to prevent back flow.",
            ontology=ontology,
        )
        self.assertNotIn(
            "pipe_or_valve_integrity_failure",
            result.fault_class_ids,
        )


class ConfidenceAndIdentityTests(unittest.TestCase):
    def test_direct_entailed_candidate_can_enter_silver(self) -> None:
        decision = decide_confidence(
            model_confidence=0.95,
            evidence_validation=SimpleNamespace(
                valid=True, evidence_level="E1", silver_eligible=True
            ),
            relation_type_validation=SimpleNamespace(valid=True),
            relation_entailment_validation=SimpleNamespace(
                status="entailed", silver_eligible=True
            ),
            source_tier="A",
        )
        self.assertEqual(decision.decision, "silver_candidate")
        self.assertEqual(decision.final_confidence, 0.95)

    def test_source_authority_does_not_change_semantic_confidence(self) -> None:
        common = {
            "model_confidence": 0.95,
            "evidence_validation": SimpleNamespace(
                valid=True, evidence_level="E1", silver_eligible=True
            ),
            "relation_type_validation": SimpleNamespace(valid=True),
            "relation_entailment_validation": SimpleNamespace(
                status="entailed", silver_eligible=True
            ),
        }
        tier_a = decide_confidence(**common, source_tier="A")
        tier_b = decide_confidence(**common, source_tier="B")
        self.assertEqual(tier_a.final_confidence, tier_b.final_confidence)
        self.assertNotEqual(
            tier_a.source_confidence_component,
            tier_b.source_confidence_component,
        )

    def test_e3_is_never_automatic_silver_but_can_be_reviewed(self) -> None:
        decision = decide_confidence(
            model_confidence=0.95,
            evidence_validation=SimpleNamespace(
                valid=True, evidence_level="E3", silver_eligible=False
            ),
            relation_type_validation=SimpleNamespace(valid=True),
            relation_entailment_validation=SimpleNamespace(
                status="undetermined", silver_eligible=False
            ),
            source_tier="A",
        )
        self.assertEqual(decision.decision, "candidate_needs_review")
        self.assertFalse(decision.silver_eligible)

    def test_explicit_non_entailment_is_rejected(self) -> None:
        decision = decide_confidence(
            model_confidence=0.99,
            evidence_validation=SimpleNamespace(
                valid=True, evidence_level="E1", silver_eligible=True
            ),
            relation_type_validation=SimpleNamespace(valid=True),
            relation_entailment_validation=SimpleNamespace(
                status="not_entailed", silver_eligible=False
            ),
        )
        self.assertEqual(decision.decision, "rejected")
        self.assertIn("relation_not_entailed", decision.rejection_reasons)

    def test_heldout_spelling_variants_are_not_automatic_silver(self) -> None:
        for split in ("held_out_test", "heldout_test"):
            with self.subTest(split=split):
                decision = decide_confidence(
                    model_confidence=0.99,
                    evidence_validation=SimpleNamespace(
                        valid=True,
                        evidence_level="E1",
                        silver_eligible=True,
                    ),
                    relation_type_validation=SimpleNamespace(valid=True),
                    relation_entailment_validation=SimpleNamespace(
                        status="entailed", silver_eligible=True
                    ),
                    document_split=split,
                )
                self.assertEqual(
                    decision.decision, "candidate_needs_review"
                )

    def test_entity_and_claim_ids_are_normalization_stable(self) -> None:
        first = stable_entity_id("Blocked  Suction Pipe", "Cause")
        second = stable_entity_id("blocked suction pipe", "Cause")
        self.assertTrue(first.startswith("MPE-"))
        self.assertEqual(first, second)
        tail = stable_entity_id("Low capacity", "Symptom")
        self.assertEqual(
            stable_claim_id(first, "causes", tail),
            stable_claim_id(second, "causes", tail),
        )

    def test_dedup_removes_only_same_claim_and_same_evidence(self) -> None:
        base = {
            "head": "Blocked suction pipe",
            "head_type": "Cause",
            "relation": "causes",
            "tail": "Low capacity",
            "tail_type": "Symptom",
            "doc_id": "MP001",
            "pdf_page_number": 2,
            "evidence_text": "Blocked suction pipe causes low capacity.",
        }
        second_evidence = {
            **base,
            "doc_id": "MP002",
            "pdf_page_number": 9,
        }
        result = deduplicate_triples([base, dict(base), second_evidence])
        self.assertEqual(result.duplicates_removed, 1)
        self.assertEqual(len(result.records), 2)
        self.assertEqual(
            len({record["claim_id"] for record in result.records}), 1
        )
        self.assertEqual(
            len({record["evidence_id"] for record in result.records}), 2
        )
        self.assertTrue(
            all(
                str(record["assertion_id"]).startswith("MPA-")
                for record in result.records
            )
        )


class CoverageGateTests(unittest.TestCase):
    @staticmethod
    def _record(
        index: int,
        *,
        head_type: str,
        tail_type: str,
        role: str,
        doc_id: str,
        source: str,
        split: str = "build_train",
    ) -> dict[str, object]:
        record = {
            "head": f"Head {index}",
            "head_type": head_type,
            "relation": "causes" if tail_type == "Symptom" else "mitigated_by",
            "tail": f"Tail {index}",
            "tail_type": tail_type,
            "doc_id": doc_id,
            "pdf_page_number": index + 1,
            "evidence_text": f"Evidence {index}",
            "evidence_start": index * 10,
            "evidence_end": index * 10 + 9,
            "evidence_level": "E1",
            "evidence_role": role,
            "relation_entailment_valid": True,
            "decision": "silver_candidate",
            "final_confidence": 0.95,
            "document_split": split,
            "source_family_id": source,
            "fault_class_ids": ["hydraulic_blockage"],
            "inferred_edge": False,
        }
        return enrich_stable_ids(record)

    def test_all_five_gate_conditions_are_conjunctive(self) -> None:
        records = [
            self._record(
                index,
                head_type="Cause",
                tail_type="Symptom",
                role="symptom",
                doc_id="MP001" if index % 2 == 0 else "MP014",
                source="ABS" if index % 2 == 0 else "IndependentVendor",
            )
            for index in range(5)
        ]
        records.extend(
            self._record(
                10 + index,
                head_type="FaultMode",
                tail_type="MaintenanceAction",
                role="inspection_or_maintenance",
                doc_id="MP001" if index == 0 else "MP014",
                source="ABS" if index == 0 else "IndependentVendor",
            )
            for index in range(2)
        )
        report = build_coverage_report(
            records, fault_ids=["hydraulic_blockage"]
        )
        item = report["fault_coverage"]["hydraulic_blockage"]
        self.assertGreaterEqual(item["symptom_evidence"], 5)
        self.assertGreaterEqual(item["cause_or_mechanism_evidence"], 3)
        self.assertEqual(item["inspection_or_maintenance_evidence"], 2)
        self.assertTrue(item["gate_passed"])

    def test_thresholds_load_from_versioned_fault_ontology(self) -> None:
        ontology = load_fault_ontology(project_root=PROJECT_ROOT)
        thresholds = CoverageThresholds.from_ontology(ontology)
        self.assertEqual(thresholds.symptom, 5)
        self.assertEqual(thresholds.cause_or_mechanism, 3)
        self.assertEqual(thresholds.inspection_or_maintenance, 2)
        self.assertEqual(thresholds.source_families, 2)

    def test_development_and_same_source_family_do_not_fill_gate(self) -> None:
        records = [
            self._record(
                index,
                head_type="Cause",
                tail_type="Symptom",
                role="symptom",
                doc_id="MP001" if index % 2 == 0 else "MP004",
                source="DESMI",
            )
            for index in range(5)
        ]
        records.extend(
            self._record(
                20 + index,
                head_type="FaultMode",
                tail_type="MaintenanceAction",
                role="inspection_or_maintenance",
                doc_id="MP001",
                source="DESMI",
            )
            for index in range(2)
        )
        records.append(
            self._record(
                99,
                head_type="Cause",
                tail_type="Symptom",
                role="symptom",
                doc_id="MP008",
                source="Grundfos",
                split="development",
            )
        )
        report = build_coverage_report(
            records,
            fault_ids=["hydraulic_blockage"],
            thresholds=CoverageThresholds(),
        )
        item = report["fault_coverage"]["hydraulic_blockage"]
        self.assertEqual(report["eligible_build_silver_records"], 7)
        self.assertEqual(item["source_families"], ["DESMI"])
        self.assertFalse(item["gate_checks"]["source_families_at_least_2"])
        self.assertFalse(item["gate_passed"])

    def test_missing_stable_source_family_is_not_eligible(self) -> None:
        record = self._record(
            101,
            head_type="Cause",
            tail_type="Symptom",
            role="symptom",
            doc_id="MP001",
            source="ABS",
        )
        record.pop("source_family_id")
        report = build_coverage_report(
            [record],
            fault_ids=["hydraulic_blockage"],
        )
        self.assertEqual(report["eligible_build_silver_records"], 0)


if __name__ == "__main__":
    unittest.main()
