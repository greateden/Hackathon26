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


def vote_identity_fixture():
    items = []
    for index, gold in enumerate(("entailment", "neutral", "contradiction", "neutral")):
        source = "synthetic://vote-identity/" + str(index)
        text = "Proposal evidence " + str(index)
        evidence = "[e1; page 1]\n" + text
        request = {
            "id": "synthetic-" + str(index),
            "task": "advanced",
            "pipeline_version": "vote-aware-v1",
            "claim": "Claim " + str(index),
            "claim_language": "de",
            "booklet": source,
            "booklet_language": "de",
            "vote": "Proposal " + str(index),
            "evidence": "retrieved",
            "top_k": 5,
        }
        passage = {
            "id": "e1", "page": 1, "text": text, "source": source,
            "pdf_sha256": "synthetic-" + str(index),
            "page_start": 0, "page_end": len(text),
        }
        evidence_hash = prompt_ab.digest(evidence.encode())
        arms = {}
        for arm in prompt_ab.ARMS:
            messages = booklet_app.build_messages(
                request["claim"], evidence, prompt_ab.PROMPTS[arm],
                vote=request["vote"], pipeline_version="vote-aware-v1")
            arms[arm] = {
                "evidence_sha256": evidence_hash,
                "prompt_sha256": prompt_ab.prompt_hash(messages),
            }
        items.append({
            "row_index": index, "cell": "de->de:" + gold, "request": request,
            "gold": gold, "pdf_sha256": "synthetic-" + str(index),
            "passages": [passage], "evidence": evidence,
            "evidence_sha256": evidence_hash, "arms": arms,
        })
    return {
        "schema": prompt_ab.SCHEMA, "phase": "vote-identity",
        "expected_rows": len(items), "planned_calls": len(items) * 2,
        "items": items,
    }


def synthetic_booklet(request):
    item = int(request["id"].rsplit("-", 1)[1])
    text = "Proposal evidence " + str(item)
    return {
        "source": request["booklet"],
        "language": request["booklet_language"],
        "sha256": "synthetic-" + str(item),
        "pages": [{"page": 1, "text": text}],
    }


class PromptPilotContracts(unittest.TestCase):
    def setUp(self):
        prompt_ab.configure_variant("prompt_pilot")

    def test_frozen_plan_has_portable_provenance(self):
        pilot = json.loads((ROOT / "docs/evidence/prompt_pilot27_plan_v1.json").read_text())
        grouped_path = ROOT / pilot["source_plan"]
        grouped = json.loads(grouped_path.read_text())
        indices = pilot["row_indices"]
        self.assertEqual(len(indices), 27)
        self.assertEqual(len(set(indices)), 27)
        self.assertTrue(set(indices).issubset(grouped["plan"]["row_indices"]))
        self.assertEqual(prompt_ab.digest(grouped_path.read_bytes()), pilot["source_plan_sha256"])

    def test_frozen_plan_is_first_grouped81_row_per_cell(self):
        dataset_path = ROOT / "data/eval/mnli_swiss_v1.1.jsonl"
        if not dataset_path.is_file():
            self.skipTest("optional evaluation dataset is unavailable; portable plan provenance was checked separately")
        pilot = json.loads((ROOT / "docs/evidence/prompt_pilot27_plan_v1.json").read_text())
        grouped = json.loads((ROOT / pilot["source_plan"]).read_text())
        rows = [json.loads(line) for line in dataset_path.read_text().splitlines()]
        first = {}
        for index in grouped["plan"]["row_indices"]:
            row = rows[index]
            cell = (row["claim_language"], row["reference_language"], row["entailment_label"])
            first.setdefault(cell, index)
        expected = [first[cell] for cell in sorted(first)]
        self.assertEqual(pilot["row_indices"], expected)
        self.assertEqual(len(expected), 27)

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
            self.assertIn("Production remains current_v1", rendered)
            self.assertNotIn("until all real calls are recorded", rendered)
            self.assertEqual(len(summary["paired_prediction_flips"]), 1)

            refreshed = prompt_ab.summarise_run(directory, prepared)
            self.assertEqual(refreshed["status"], "COMPLETE_WITH_ERRORS")
            for record in records:
                wrong = "neutral" if record["gold"] != "neutral" else "entailment"
                record.update(status="completed", pred=record["gold"] if record["arm"] == "teammate_rules_v1" else wrong,
                              correct=record["arm"] == "teammate_rules_v1")
                record["result"]["error"] = None
            (directory / "predictions.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))
            prompt_ab.summarise_run(directory, prepared)
            self.assertNotIn("refined prompt did not improve accuracy", (directory / "summary.md").read_text())

    def test_vote_identity_frozen_e2e_mock_keeps_hashes_results_and_accounting(self):
        prompt_ab.configure_variant("vote_identity")
        prepared = vote_identity_fixture()
        for item in prepared["items"]:
            booklet = synthetic_booklet(item["request"])
            item["passages"] = booklet_app.source_passages(booklet, item["passages"])
            item["evidence"] = booklet_app.candidate_evidence(item["passages"])
            item["evidence_sha256"] = prompt_ab.digest(item["evidence"].encode())
            for arm in prompt_ab.ARMS:
                messages = booklet_app.build_messages(
                    item["request"]["claim"], item["evidence"],
                    prompt_ab.PROMPTS[arm], vote=item["request"]["vote"],
                    pipeline_version="vote-aware-v1")
                item["arms"][arm]["evidence_sha256"] = item["evidence_sha256"]
                item["arms"][arm]["prompt_sha256"] = prompt_ab.prompt_hash(messages)
        prompt_ab.validate_prepared(prepared)

        class MockJudge:
            def __init__(self, response):
                self.response = response

            def judge(self, *args, **kwargs):
                return dict(self.response)

        records = []
        labels = ("entailment", "neutral", "contradiction", None)
        for item, label in zip(prepared["items"][:4], labels):
            booklet = synthetic_booklet(item["request"])
            for arm in prompt_ab.ARMS:
                messages = booklet_app.build_messages(
                    item["request"]["claim"], item["evidence"],
                    prompt_ab.PROMPTS[arm], vote=item["request"]["vote"],
                    pipeline_version="vote-aware-v1")
                self.assertEqual(prompt_ab.prompt_hash(messages),
                                 item["arms"][arm]["prompt_sha256"])
                valid = label is not None
                response = {
                    "label": label if valid else None,
                    "label_code": {"entailment": 0, "neutral": 1,
                                   "contradiction": 2}.get(label),
                    "reasoning": "offline fixture",
                    "raw_response": '{"label":"%s"}' % label,
                    "usage": {"prompt_tokens": 11, "completion_tokens": 3},
                    "input_tokens": 11, "inference_s": 0.01,
                    "error": None if valid else "vote_unrecognised",
                    "citation_verified": valid,
                }
                if arm == "candidate":
                    response.update(
                        vote_status="recognised" if valid else "unrecognised",
                        vote_reference={"passage_id": "e1"} if valid else None,
                        evidence_status=("insufficient" if label == "neutral"
                                          else "sufficient") if valid else "insufficient",
                        evidence_refs=([{"passage_id": "e1"}]
                                       if valid and label != "neutral" else []))
                result = prompt_ab.classify(
                    item["request"], MockJudge(response),
                    prompt_ab.FrozenRetriever(item["passages"]), booklet)
                self.assertEqual(
                    prompt_ab.digest(prompt_ab.candidate_evidence(result["passages"]).encode()),
                    item["evidence_sha256"])
                self.assertEqual(result["raw_response"], response["raw_response"])
                pred = result.get("label") if not result.get("error") else None
                records.append({
                    "schema": prompt_ab.SCHEMA,
                    "key": str(item["row_index"]) + ":" + arm,
                    "attempt_id": str(item["row_index"]) + arm,
                    "row_index": item["row_index"], "arm": arm,
                    "gold": item["gold"], "pred": pred, "correct": pred == item["gold"],
                    "elapsed_s": 0.01, "evidence_sha256": item["evidence_sha256"],
                    "status": "completed" if pred else "failed",
                    "result": result})

        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "predictions.jsonl"
            target.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records))
            summary = prompt_ab.summarise_run(Path(temporary), prepared, "COMPLETE_WITH_ERRORS")
            self.assertEqual(summary["attempts"], 8)
            self.assertEqual(summary["recorded"], 8)
            self.assertEqual(summary["arms"]["baseline"]["n"], 4)
            self.assertEqual(summary["arms"]["candidate"]["n"], 4)
            self.assertEqual(summary["arms"]["candidate"]["failed_requests"], 1)
            self.assertEqual(len(summary["evidence_identity"]), 4)
            self.assertTrue(all(row["identical"] for row in summary["evidence_identity"]))


if __name__ == "__main__":
    unittest.main()
