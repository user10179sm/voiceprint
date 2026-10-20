"""Conversational collection, consent, resumption and independent validation."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from voiceprint import context, onboarding as O, store
from voiceprint.corpus import NoCorpus
from voiceprint.elicit import PROMPTS
from voiceprint.mcp import handle

TRAINING = (
    "I started the project because the old way was wasting time. The first "
    "version was small and I could explain every choice. When a friend tried "
    "it we found a problem I had missed. I changed the order of the steps "
    "and asked them to try again. That helped me understand what mattered. "
) * 30
VALIDATION = (
    "My favourite part of teaching was watching someone work something out. "
    "Sometimes a different example helped more than another explanation. "
    "At other times we needed a break before coming back to the question. "
    "Those afternoons taught me to listen carefully rather than jump straight "
    "into giving advice. People often knew more than they realised. "
) * 10


class Context(unittest.TestCase):
    def test_applications_and_email_are_automatic(self):
        for task in ("Answer this job application question", "Write a cover letter",
                     "I'm filling out an application for a job", "Why our company?"):
            self.assertEqual(context.infer(task).register, "application", task)
        self.assertEqual(context.infer("Email the recruiter about my job application").register,
                         "email")

    def test_host_uses_full_conversation_when_keywords_are_ambiguous(self):
        self.assertEqual(context.resolve("Tell us about a challenge", "application").register,
                         "application")
        with self.assertRaises(ValueError):
            context.resolve("anything", "invented")

    def test_existing_contexts_still_work(self):
        for task, register in (("reply to Sam", "email"), ("slack message", "chat"),
                               ("board report", "report"), ("README guide", "docs")):
            self.assertEqual(context.infer(task).register, register)


class Onboarding(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"VOICEPRINT_HOME": self.tmp.name})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def add(self, text=TRAINING, **kwargs):
        values = dict(name="tester", text=text, source="pasted", origin="original note",
                      authorship="human", register="application")
        values.update(kwargs)
        return O.add_sample(**values)

    def skip_sources(self):
        for source in O.SOURCES:
            O.decide_source("tester", source, "declined")

    def test_source_suggestion_tracks_task_without_reading_anything(self):
        with patch("voiceprint.ingest.read_path", side_effect=AssertionError("read a source")):
            first = O.status("tester", "job application")
            self.assertEqual(first["next_step"]["source"], "applications")
            result = O.decide_source("tester", "applications", "declined")
        self.assertNotEqual(result["next_step"]["source"], "applications")
        self.assertFalse(store.exists("tester"))

    def test_source_requires_agreement_and_scope(self):
        with self.assertRaisesRegex(ValueError, "not agreed"):
            self.add(source="sent_email")
        with self.assertRaisesRegex(ValueError, "scope"):
            O.decide_source("tester", "sent_email", "accepted")
        O.decide_source("tester", "sent_email", "accepted", "Two selected sent emails")
        self.add(source="sent_email", register=None)
        self.assertIn("email", O.status("tester")["words_by_register"])

    def test_unknown_and_assisted_authorship_never_enter_session(self):
        O.status("tester")
        for authorship in ("unknown", "assisted"):
            with self.assertRaisesRegex(ValueError, "original human"):
                self.add(authorship=authorship)
        self.assertEqual(O.status("tester")["training_words"], 0)
        self.assertNotIn(TRAINING.strip(), O.path_for("tester").read_text())

    def test_progress_survives_a_new_process_without_raw_text_in_status(self):
        self.add()
        result = subprocess.run([sys.executable, "-c",
            "import json\nfrom voiceprint.onboarding import status\n"
            "print(json.dumps(status('tester')))"], capture_output=True, text=True, check=True)
        loaded = json.loads(result.stdout)
        self.assertGreater(loaded["training_words"], 1000)
        self.assertNotIn("text", loaded["samples"][0])
        self.assertEqual(json.loads(O.path_for("tester").read_text())["samples"][0]["text"],
                         TRAINING.strip())
        if os.name != "nt":
            self.assertEqual(O.path_for("tester").stat().st_mode & 0o777, 0o600)

    def test_prompt_matches_task_then_moves_on_after_answer(self):
        O.status("tester", "job application")
        self.skip_sources()
        first = O.status("tester")["next_step"]
        self.assertEqual(first["register"], "application")
        self.assertGreaterEqual(first["suggested_words"], 400)
        self.add(source="prompt", prompt=first["prompt_id"], register=None)
        second = O.status("tester")["next_step"]
        self.assertNotEqual(first["prompt_id"], second["prompt_id"])
        self.assertEqual(second["register"], "application")

    def test_unknown_task_gets_a_general_writing_prompt(self):
        self.skip_sources()
        self.assertEqual(O.status("tester")["next_step"]["register"], "note")

    def test_pooled_volume_does_not_hide_a_missing_context(self):
        self.add(TRAINING * 4, register="email")
        self.skip_sources()
        result = O.status("tester", "job application")
        self.assertGreater(result["training_words"], 5000)
        self.assertEqual(result["next_step"]["kind"], "prompt")
        self.assertEqual(result["next_step"]["register"], "application")

    def test_sufficient_current_context_skips_unnecessary_source_questions(self):
        self.add(TRAINING * 4)
        result = O.status("tester", "job application")
        self.assertEqual(result["next_step"]["kind"], "validation")

    def test_prompt_policy_fills_gaps_after_context_has_material(self):
        chosen = O.choose_prompt(PROMPTS, "application", {"application": 6000, "note": 500})
        self.assertNotEqual(chosen.register, "application")
        self.assertEqual(O.choose_prompt([], "application", {}), None)

    def test_duplicate_and_normalised_duplicate_do_not_inflate_counts(self):
        first = self.add()
        for text in (TRAINING, TRAINING.upper().replace(" ", "  ")):
            with self.assertRaisesRegex(ValueError, "already"):
                self.add(text)
        self.assertEqual(first["training_words"], O.status("tester")["training_words"])

    def test_validation_cannot_reuse_training_or_an_excerpt(self):
        self.add()
        for text in (TRAINING, " ".join(TRAINING.split()[5:65]),
                     VALIDATION + " ".join(TRAINING.split()[10:50])):
            with self.assertRaises(ValueError):
                self.add(text, purpose="validation")
        self.assertEqual(O.status("tester")["validation_samples"], 0)

    def test_validation_cannot_later_become_training(self):
        self.add(VALIDATION, purpose="validation")
        with self.assertRaises(ValueError):
            self.add(VALIDATION)

    def test_source_decisions_can_be_reversed_and_scope_narrowed(self):
        O.decide_source("tester", "applications", "declined")
        O.decide_source("tester", "applications", "accepted", "Two originals")
        self.add(source="applications")
        result = O.decide_source("tester", "applications", "accepted", "One original")
        self.assertEqual(result["removed_samples"], 1)
        self.add(source="applications")
        result = O.decide_source("tester", "applications", "declined")
        self.assertEqual(result["training_words"], 0)

    def test_transcripts_do_not_inflate_written_profile(self):
        O.decide_source("tester", "transcripts", "accepted", "One voice note")
        self.add(source="transcripts")
        result = O.status("tester")
        self.assertEqual(result["training_words"], 0)
        self.assertGreater(result["spoken_words"], 0)
        with self.assertRaises(NoCorpus):
            O.finish("tester")

    def test_finish_requires_training_and_separate_validation(self):
        with self.assertRaises(NoCorpus):
            O.finish("tester")
        self.add()
        with self.assertRaisesRegex(NoCorpus, "validation"):
            O.finish("tester")
        self.assertFalse(store.exists("tester"))

    def test_build_excludes_held_out_words_and_protects_existing_profile(self):
        first = self.add()
        self.add(VALIDATION, purpose="validation", origin="held-out note")
        result = O.finish("tester")
        saved = store.load("tester")
        self.assertEqual(saved.words, first["training_words"])
        self.assertEqual([s["origin"] for s in saved.manifest], ["original note"])
        self.assertEqual(len(result["validation"]), 1)
        self.assertEqual(result["validation"][0]["profile_register"], "application")
        self.assertNotIn("accuracy", result)
        with self.assertRaises(store.ProfileExists):
            O.finish("tester")

    def test_small_collection_can_build_but_reports_its_limits(self):
        self.add(" ".join(TRAINING.split()[:70]))
        self.add(" ".join(VALIDATION.split()[:65]), purpose="validation")
        result = O.finish("tester")
        self.assertEqual(result["confidence"], "provisional")
        self.assertFalse(result["validation"][0]["report"]["reliable"])
        self.assertTrue(result["limitations"])

    def test_rejected_samples_do_not_damage_saved_progress(self):
        initial = self.add()
        for changes in ({"text": "too short"}, {"register": "invented"},
                        {"prompt": "invented"}, {"purpose": "invented"}):
            with self.assertRaises(ValueError):
                self.add(**{"text": VALIDATION, **changes})
        self.assertEqual(O.status("tester")["training_words"], initial["training_words"])

    def call(self, tool, **arguments):
        return handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": tool, "arguments": arguments}})["result"]

    def test_full_conversation_through_mcp_tools(self):
        start = self.call("voiceprint_onboard", name="tester", task="job application")
        self.assertFalse(start["isError"])
        decision = self.call("voiceprint_source_decision", name="tester", source="applications",
                             decision="accepted", scope="Selected original application answer")
        self.assertFalse(decision["isError"])
        for prose, purpose in ((TRAINING, "training"), (VALIDATION, "validation")):
            response = self.call("voiceprint_add_sample", name="tester", text=prose,
                                 source="applications", origin=purpose, authorship="human",
                                 purpose=purpose)
            self.assertFalse(response["isError"], response)
        finished = self.call("voiceprint_finish_onboarding", name="tester")
        self.assertFalse(finished["isError"], finished)
        for tool, extra in (("voiceprint_brief", {}), ("voiceprint_check", {"draft": VALIDATION})):
            response = self.call(tool, name="tester", task="Tell us about a challenge",
                                 register="application", **extra)
            self.assertFalse(response["isError"], response)
        response = self.call("voiceprint_brief", name="tester", task="Email my colleague")
        self.assertIn("pooled profile", response["content"][0]["text"])

    def test_mcp_reports_declined_sources_as_errors(self):
        result = self.call("voiceprint_add_sample", name="tester", text=TRAINING,
                           source="applications", origin="not agreed", authorship="human")
        self.assertTrue(result["isError"])

    def test_revoked_source_blocks_writing_until_profile_is_rebuilt(self):
        O.decide_source("tester", "applications", "accepted", "Selected original answer")
        self.add(source="applications")
        self.add(VALIDATION, purpose="validation")
        O.finish("tester")
        O.decide_source("tester", "applications", "declined")
        self.assertTrue(O.status("tester")["profile_stale"])
        self.assertTrue(self.call("voiceprint_brief", name="tester")["isError"])
        self.assertTrue(self.call("voiceprint_check", name="tester", draft=VALIDATION)["isError"])
        self.add(TRAINING)
        O.finish("tester", overwrite=True)
        self.assertFalse(O.status("tester")["profile_stale"])
        self.assertFalse(self.call("voiceprint_brief", name="tester")["isError"])


if __name__ == "__main__":
    unittest.main()
