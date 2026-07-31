#!/usr/bin/env python3
"""Reviewer edge-case tests for CulturalExchangeHub (solution.py).

Covers gaps not exercised by the implementer's suite (test_solution.py):
  - sending a message from a user outside the partnership
  - messages_for on an unknown partnership id
  - profile picture default in the update path
  - update_profile unknown user -> NotFound
  - translation from unknown language pair -> passthrough
  - feedback averages partitioned by target_type (same id, diff type)
  - build() idempotence at a repeated stage
  - stage-2 tour enrichment language field
"""
import unittest

from solution import (CulturalExchangeHub, DependencyError, InvalidInputError,
                      NotFoundError)


class TestReviewerEdge(unittest.TestCase):
    def setUp(self):
        self.hub = CulturalExchangeHub()
        self.hub.build(5)
        self.a = self.hub.profiles.create_user("a", "a@x.com")
        self.b = self.hub.profiles.create_user("b", "b@x.com")

    def test_sender_not_in_partnership(self):
        pid = self.hub.language.pair_users(self.a, self.b)
        c = self.hub.profiles.create_user("c", "c@x.com")
        with self.assertRaises(InvalidInputError):
            self.hub.language.send_message(pid, c, "hello")

    def test_messages_for_unknown_partnership(self):
        with self.assertRaises(NotFoundError):
            self.hub.language.messages_for(999)

    def test_update_profile_unknown_user(self):
        with self.assertRaises(NotFoundError):
            self.hub.profiles.update_profile(999, interests="x")

    def test_empty_picture_default_via_update(self):
        self.hub.profiles.update_profile(self.a, profile_picture="")
        self.assertEqual(
            self.hub.profiles.get_user(self.a)["profile_picture"],
            "default_avatar.png")

    def test_unknown_language_pair_passthrough(self):
        self.assertEqual(
            self.hub.language.get_translation("hello", "xx", "yy"), "hello")

    def test_feedback_partitioned_by_type(self):
        self.hub.feedback.submit_feedback("tour", 1, self.a, 5)
        self.hub.feedback.submit_feedback("exchange", 1, self.b, 1)
        self.assertEqual(self.hub.feedback.average_rating("tour", 1), 5.0)
        self.assertEqual(self.hub.feedback.average_rating("exchange", 1), 1.0)

    def test_build_idempotent(self):
        h = CulturalExchangeHub()
        self.assertEqual(h.build(2), 2)
        self.assertEqual(h.build(2), 2)   # re-invoke same stage: no error
        self.assertEqual(h.build(3), 3)
        self.assertEqual(h.stage(), 3)

    def test_stage2_allows_tours_only_after_user(self):
        h = CulturalExchangeHub()
        before = CulturalExchangeHub()  # stage 0
        with self.assertRaises(DependencyError):
            before.tours.create_tour("T", 1, "m.glb")
        h.build(2)
        owner = h.profiles.create_user("o", "o@x.com")
        tid = h.tours.create_tour("T", owner, "m.glb")
        h.tours.add_hotspot(tid, "L", "info", (0, 0, 0))
        h.tours.add_audio_guide(tid, "G", "a.mp3", "fr")
        t = h.tours.get_tour(tid)
        self.assertEqual(len(t["hotspots"]), 1)
        self.assertEqual(len(t["audio_guides"]), 1)
        self.assertEqual(t["audio_guides"][0]["language"], "fr")


if __name__ == "__main__":
    unittest.main(verbosity=2)
