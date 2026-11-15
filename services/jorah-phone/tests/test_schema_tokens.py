import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jorah_phone import schema  # noqa: E402
from jorah_phone.tokens import TokenError, Tokens, digest, listing, new_token, revoke, write_token_file  # noqa: E402

NAMES = ("ask-request", "ask-response", "event", "health", "today", "events")


class SchemaTest(unittest.TestCase):
    def test_every_contract_schema_loads(self):
        for name in NAMES:
            with self.subTest(name=name):
                self.assertEqual(schema.load(name)["properties"]["v"], {"const": 1})

    def test_the_contract_examples_pass(self):
        examples = schema.CONTRACTS / "examples"
        for name, file in (("today", "today-ok.json"), ("events", "events-ok.json"), ("event", "event-arrive.json"),
                           ("health", "health-upload.json"), ("ask-request", "ask.json")):
            with self.subTest(file=file):
                schema.validate(schema.load(name), json.loads((examples / file).read_text()))

    def test_a_keyword_the_checker_doesnt_do_is_refused(self):
        for bad in ({"type": "object", "oneOf": []}, {"type": "object", "additionalProperties": True},
                    {"type": "string", "format": "email"}, {"type": "thing"},
                    {"type": "object", "required": ["x"], "properties": {}}):
            with self.subTest(bad=bad), self.assertRaises(schema.SchemaError):
                schema.check_schema(bad)

    def test_values(self):
        event = schema.load("event")
        good = {"v": 1, "kind": "arrive", "place": "home", "at": "2026-11-15T07:52:10+01:00"}
        schema.validate(event, good)
        for bad in (
            {**good, "v": True},                      # true is not 1
            {**good, "v": 1.0},                       # nor is 1.0
            {**good, "kind": "teleport"},
            {**good, "lat": 48.1},                    # unknown fields never pass
            {k: v for k, v in good.items() if k != "at"},
            {**good, "at": "2026-11-15T07:52:10"},    # no offset
            {**good, "at": "yesterday"},
            {**good, "at": "2026-11-15T07:52:10+01:00" + "x" * 40},
        ):
            with self.subTest(bad=bad), self.assertRaises(schema.Invalid):
                schema.validate(event, bad)

    def test_date_times(self):
        for ok in ("2026-11-15T07:52+01:00", "2026-11-15T07:52:10Z", "2026-11-15T07:52:10.123456+0100", "2026-03-29T02:30:00-05:00"):
            self.assertIsNotNone(schema.parse_date_time(ok), ok)
        for bad in ("2026-11-15", "2026-11-15T07:52:10", "2026-13-15T07:52:10Z", "2026-11-15T07:52:10.1234567Z", 5, None):
            self.assertIsNone(schema.parse_date_time(bad), bad)

    def test_numbers_must_be_finite_and_integers_must_be_whole(self):
        health = schema.load("health")
        sample = {"v": 1, "sent_at": "2026-11-15T07:00:00+01:00", "sleep": [], "resting_hr": [], "workouts": [],
                  "hrv": [{"at": "2026-11-15T03:00:00+01:00", "ms": 41.5}]}
        schema.validate(health, sample)
        nan = json.loads('{"at": "2026-11-15T03:00:00+01:00", "ms": NaN}')
        with self.assertRaises(schema.Invalid):
            schema.validate(health, {**sample, "hrv": [nan]})
        with self.assertRaises(schema.Invalid):
            schema.validate({"type": "integer"}, 3.0)
        with self.assertRaises(schema.Invalid):
            schema.validate({"type": "integer"}, False)

    def test_the_problem_is_named_by_place_not_value(self):
        with self.assertRaises(schema.Invalid) as caught:
            schema.validate(schema.load("ask-request"), {"v": 1, "text": "Zeltrova-7Q " * 60})
        self.assertNotIn("Zeltrova", str(caught.exception))
        self.assertEqual(caught.exception.path, "$.text")


class TokensTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.file = Path(self.dir.name) / "cfg" / "tokens.json"

    def tearDown(self):
        self.dir.cleanup()

    def test_a_token_is_stored_only_as_a_hash(self):
        token = new_token(self.file, "iphone", ["ingest", "ask"])
        text = self.file.read_text()
        self.assertNotIn(token, text)
        self.assertIn(digest(token), text)
        self.assertEqual(stat.S_IMODE(self.file.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.file.parent.stat().st_mode), 0o700)
        self.assertEqual(listing(self.file)[0]["scopes"], ["ask", "ingest"])

    def test_scopes_and_revoke(self):
        phone = new_token(self.file, "iphone", ["ask", "ingest"])
        reader = new_token(self.file, "gateway", ["read"])
        tokens = Tokens(self.file)
        self.assertEqual(tokens.check(f"Bearer {phone}", "ask"), "iphone")
        self.assertIsNone(tokens.check(f"Bearer {phone}", "read"))
        self.assertEqual(tokens.check(f"Bearer {reader}", "read"), "gateway")
        for bad in (None, "", phone, f"Basic {phone}", "Bearer ", f"Bearer {phone}x", f"Bearer {'a' * 300}"):
            self.assertIsNone(tokens.check(bad, "ask"), bad)
        self.assertTrue(revoke(self.file, "iphone"))
        self.assertIsNone(tokens.check(f"Bearer {phone}", "ask"))   # at once, same Tokens object
        self.assertEqual(tokens.check(f"Bearer {reader}", "read"), "gateway")
        self.assertFalse(revoke(self.file, "iphone"))

    def test_ids_and_duplicates(self):
        new_token(self.file, "iphone", ["ask"])
        with self.assertRaises(TokenError):
            new_token(self.file, "iphone", ["ask"])
        again = new_token(self.file, "iphone", ["ask"], replace=True)
        self.assertEqual(len(listing(self.file)), 1)
        self.assertEqual(Tokens(self.file).check(f"Bearer {again}", "ask"), "iphone")
        for bad_id in ("", "iPhone", "-x", "a" * 33, "a b"):
            with self.assertRaises(TokenError):
                new_token(self.file, bad_id, ["ask"])
        with self.assertRaises(TokenError):
            new_token(self.file, "x", ["admin"])

    def test_an_unsafe_or_broken_file_lets_nothing_through(self):
        token = new_token(self.file, "iphone", ["ask"])
        os.chmod(self.file, 0o644)
        tokens = Tokens(self.file)
        self.assertIsNone(tokens.check(f"Bearer {token}", "ask"))
        self.assertIn("owner only", tokens.problem)
        os.chmod(self.file, 0o600)
        self.file.write_text('{"v": 1, "tokens": [{"id": "x", "sha256": "nothex", "scopes": ["ask"]}]}')
        self.assertIsNone(Tokens(self.file).check(f"Bearer {token}", "ask"))

    def test_a_missing_file_means_no_tokens(self):
        tokens = Tokens(self.file)
        self.assertIsNone(tokens.check("Bearer abc", "ask"))
        self.assertIsNone(tokens.problem)

    def test_token_file_for_the_plugin(self):
        target = Path(self.dir.name) / "cfg" / "read-token"
        write_token_file(target, "secret-value")
        self.assertEqual(target.read_text().strip(), "secret-value")
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)


if __name__ == "__main__":
    unittest.main()
