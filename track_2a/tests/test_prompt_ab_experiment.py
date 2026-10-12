"""Offline contracts for the frozen prompt-only pilot."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import booklet_app
from labels import CODE_TO_LABEL
import prompt_ab_experiment as prompt_ab


ROOT = Path(__file__).resolve().parents[1]


def prepared_fixture():
    items = []
    index = 0
    for claim in ("de", "fr", "it"):
        for evidence_language in ("de", "fr", "it"):
            for gold in CODE_TO_LABEL.values():
                evidence = "[page 1]\nEvidence " + str(index)
                evidence_hash = prompt_ab.digest(evidence.encode())
                request = {"claim": "Claim " + str(index), "claim_language": claim,
                           "booklet": "https://example.test/" + str(index) + ".pdf",
                           "booklet_language": evidence_language, "evidence": "retrieved", "top_k": 5}
                arms = {}
                for arm in prompt_ab.ARMS:
                    messages = booklet_app.build_messages(request["claim"], evidence, prompt_ab.PROMPTS[arm])
                    arms[arm] = {"evidence_sha256": evidence_hash,
                                 "prompt_sha256": prompt_ab.prompt_hash(messages)}
                items.append({"row_index": index, "cell": claim + "->" + evidence_language + ":" + gold,
                              "request": request, "gold": gold, "pdf_sha256": "pdf",
                              "passages": [], "evidence": evidence, "evidence_sha256": evidence_hash,
                              "arms": arms})
                index += 1
    return {"schema": prompt_ab.SCHEMA, "phase": "pilot", "expected_rows": 27,
            "planned_calls": 54, "items": items}


class PromptPilotContracts(unittest.TestCase):
    def test_frozen_plan_is_first_grouped81_row_per_cell(self):
        pilot = json.loads((ROOT / "docs/evidence/prompt_pilot27_plan_v1.json").read_text())
        grouped_path = ROOT / pilot["source_plan"]
        grouped = json.loads(grouped_path.read_text())
        rows = [json.loads(line) for line in (ROOT / "data/eval/mnli_swiss_v1.1.jsonl").read_text().splitlines()]
        first = {}
        for index in grouped["plan"]["row_indices"]:
            row = rows[index]
            cell = (row["claim_language"], row["reference_language"], row["entailment_label"])
            first.setdefault(cell, index)
        expected = [first[cell] for cell in sorted(first)]
        self.assertEqual(pilot["row_indices"], expected)
        self.assertEqual(len(expected), 27)
        self.assertEqual(prompt_ab.digest(grouped_path.read_bytes()), pilot["source_plan_sha256"])

    def test_prompt_contract_and_production_default_are_unchanged(self):
        default = booklet_app.build_messages("claim", "evidence")
        current = booklet_app.build_messages("claim", "evidence", prompt_ab.PROMPTS["current_v1"])
        self.assertEqual(default, current)
        self.assertEqual(default[0]["content"], prompt_ab.SYSTEM_PROMPT)
        self.assertNotEqual(prompt_ab.PROMPTS["current_v1"], prompt_ab.PROMPTS["teammate_rules_v1"])
        # Gold is not an input to message construction: changing it cannot alter a prompt.
        for gold in CODE_TO_LABEL.values():
            self.assertEqual(booklet_app.build_messages("claim", "evidence", prompt_ab.PROMPTS["current_v1"]), default)

    def test_27_cells_54_calls_identical_evidence_and_alternating_order(self):
        prepared = prompt_ab.validate_prepared(prepared_fixture())
        schedule = prompt_ab.call_schedule(prepared["items"])
        self.assertEqual(len(schedule), 54)
        self.assertEqual(len({(item["row_index"], arm) for item, arm in schedule}), 54)
        for position in range(27):
            pair = [arm for _, arm in schedule[position * 2:position * 2 + 2]]
            self.assertEqual(pair, list(prompt_ab.ARMS if position % 2 == 0 else reversed(prompt_ab.ARMS)))
        broken = prepared_fixture()
        broken["items"][0]["arms"]["teammate_rules_v1"]["evidence_sha256"] = "different"
        with self.assertRaisesRegex(ValueError, "byte-identical"):
            prompt_ab.validate_prepared(broken)

    def test_failures_remain_in_metrics_denominator_and_flips_are_paired(self):
        prepared = prepared_fixture()
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            records = []
            for item in prepared["items"]:
                for arm in prompt_ab.ARMS:
                    failed = item["row_index"] == 0 and arm == "current_v1"
                    pred = None if failed else item["gold"]
                    if item["row_index"] == 1 and arm == "teammate_rules_v1":
                        pred = "contradiction" if item["gold"] != "contradiction" else "neutral"
                    records.append({"schema": prompt_ab.SCHEMA, "key": str(item["row_index"]) + ":" + arm,
                                    "attempt_id": str(item["row_index"]) + arm, "row_index": item["row_index"],
                                    "arm": arm, "gold": item["gold"], "pred": pred,
                                    "correct": pred == item["gold"], "elapsed_s": 1.0,
                                    "evidence_sha256": item["evidence_sha256"],
                                    "status": "failed" if failed else "completed",
                                    "result": {"error": "request_failed" if failed else None,
                                               "citation_verified": not failed,
                                               "usage": {"prompt_tokens": 10 if arm == "current_v1" else 12,
                                                         "completion_tokens": 2}}})
            (directory / "predictions.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))
            summary = prompt_ab.summarise_run(directory, prepared, "COMPLETE_WITH_ERRORS")
            self.assertEqual(summary["arms"]["current_v1"]["n"], 27)
            self.assertEqual(summary["arms"]["current_v1"]["failed_requests"], 1)
            self.assertEqual(summary["arms"]["current_v1"]["accuracy"], 0.963)
            self.assertEqual(summary["arms"]["current_v1"]["prompt_tokens_total"], 270)
            self.assertEqual(summary["arms"]["teammate_rules_v1"]["prompt_tokens_total"], 324)
            self.assertEqual(summary["arms"]["current_v1"]["completion_tokens_total"], 54)
            prompt_ab.summarise_run(directory, prepared, "COMPLETE")
            rendered = (directory / "summary.md").read_text()
            self.assertIn("keep current_v1", rendered)
            self.assertNotIn("until all real calls are recorded", rendered)
            self.assertEqual(len(summary["paired_prediction_flips"]), 1)


if __name__ == "__main__":
    unittest.main()
