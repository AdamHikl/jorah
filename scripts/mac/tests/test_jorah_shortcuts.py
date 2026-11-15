"""Tests for scripts/mac/jorah_shortcuts.py: the Ask Jorah and Share to Jorah shortcuts follow the
jorah-phone contract and carry no token. No Mac or phone needed."""

import contextlib
import importlib.util
import io
import re
import plistlib
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("jorah_shortcuts", HERE.parent / "jorah_shortcuts.py")
shortcut = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shortcut)


class AskJorahShortcutTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.file = Path(self.dir.name) / "ask.shortcut"
        with contextlib.redirect_stdout(io.StringIO()):
            shortcut.main(["ask", str(self.file)])
        self.plist = plistlib.loads(self.file.read_bytes())
        self.actions = self.plist["WFWorkflowActions"]

    def tearDown(self):
        self.dir.cleanup()

    def params(self, n):
        return self.actions[n]["WFWorkflowActionParameters"]

    def test_the_five_steps(self):
        self.assertEqual([a["WFWorkflowActionIdentifier"].rsplit(".", 1)[1] for a in self.actions],
                         ["gettext", "dictatetext", "downloadurl", "getvalueforkey", "speaktext"])
        self.assertEqual(self.plist["WFWorkflowImportQuestions"], [])

    def test_no_token_inside(self):
        self.assertEqual(self.params(0)["WFTextActionText"], "")
        def strings(value):
            if isinstance(value, dict):
                for v in value.values():
                    yield from strings(v)
            elif isinstance(value, list):
                for v in value:
                    yield from strings(v)
            elif isinstance(value, str):
                yield value
        uuid_like = re.compile(r"^[0-9A-F]{8}(-[0-9A-F]{4}){3}-[0-9A-F]{12}$")
        # token_urlsafe(32) gives 43 characters of A-Z, a-z, 0-9, - and _.
        tokenish = [v for v in strings(self.plist) if re.fullmatch(r"[A-Za-z0-9_-]{30,}", v) and not uuid_like.match(v) and not v.startswith("WF")]
        self.assertEqual(tokenish, [])

    def test_the_request_matches_the_contract(self):
        p = self.params(2)
        self.assertEqual((p["WFURL"], p["WFHTTPMethod"], p["WFHTTPBodyType"]), (shortcut.URL, "POST", "JSON"))
        header = p["WFHTTPHeaders"]["Value"]["WFDictionaryFieldValueItems"][0]
        self.assertEqual(header["WFKey"]["Value"]["string"], "Authorization")
        value = header["WFValue"]["Value"]
        self.assertEqual(value["string"], "Bearer ￼")
        self.assertEqual(value["attachmentsByRange"]["{7, 1}"]["OutputUUID"], self.params(0)["UUID"])
        body = {i["WFKey"]["Value"]["string"]: i for i in p["WFJSONValues"]["Value"]["WFDictionaryFieldValueItems"]}
        self.assertEqual(sorted(body), ["text", "v"])   # ask-request.schema.json: exactly v and text
        self.assertEqual((body["v"]["WFItemType"], body["v"]["WFValue"]["Value"]["string"]), (3, "1"))
        self.assertEqual(body["text"]["WFValue"]["Value"]["attachmentsByRange"]["{0, 1}"]["OutputUUID"], self.params(1)["UUID"])

    def test_it_speaks_the_say_field(self):
        self.assertEqual(self.params(3)["WFDictionaryKey"], "say")
        self.assertEqual(self.params(3)["WFInput"]["Value"]["OutputUUID"], self.params(2)["UUID"])
        self.assertEqual(self.params(4)["WFText"]["Value"]["attachmentsByRange"]["{0, 1}"]["OutputUUID"], self.params(3)["UUID"])


def _strings(value):
    if isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)
    elif isinstance(value, str):
        yield value


class ShareToJorahShortcutTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.file = Path(self.dir.name) / "share.shortcut"
        with contextlib.redirect_stdout(io.StringIO()):
            shortcut.main(["share", str(self.file)])
        self.plist = plistlib.loads(self.file.read_bytes())
        self.actions = self.plist["WFWorkflowActions"]

    def tearDown(self):
        self.dir.cleanup()

    def params(self, n):
        return self.actions[n]["WFWorkflowActionParameters"]

    def test_it_is_a_share_sheet_shortcut(self):
        self.assertEqual(self.plist["WFWorkflowTypes"], ["ActionExtension"])
        self.assertIn("WFStringContentItem", self.plist["WFWorkflowInputContentItemClasses"])
        self.assertEqual(self.plist["WFWorkflowNoInputBehavior"]["Name"], "WFWorkflowNoInputBehaviorGetClipboard")
        self.assertEqual([a["WFWorkflowActionIdentifier"].rsplit(".", 1)[1] for a in self.actions],
                         ["gettext", "ask", "downloadurl", "getvalueforkey", "notification"])

    def test_the_request_matches_the_share_contract(self):
        p = self.params(2)
        self.assertEqual((p["WFURL"], p["WFHTTPMethod"], p["WFHTTPBodyType"]), (shortcut.SHARE_URL, "POST", "JSON"))
        body = {i["WFKey"]["Value"]["string"]: i for i in p["WFJSONValues"]["Value"]["WFDictionaryFieldValueItems"]}
        self.assertEqual(sorted(body), ["note", "source", "text", "v"])   # share-request.schema.json allows exactly these
        self.assertEqual(body["text"]["WFValue"]["Value"]["attachmentsByRange"]["{0, 1}"], {"Type": "ExtensionInput"})
        self.assertEqual(body["note"]["WFValue"]["Value"]["attachmentsByRange"]["{0, 1}"]["OutputUUID"], self.params(1)["UUID"])
        self.assertEqual(body["source"]["WFValue"]["Value"]["string"], "other")
        header = p["WFHTTPHeaders"]["Value"]["WFDictionaryFieldValueItems"][0]["WFValue"]["Value"]
        self.assertEqual(header["attachmentsByRange"]["{7, 1}"]["OutputUUID"], self.params(0)["UUID"])

    def test_no_token_inside_and_a_notification_at_the_end(self):
        self.assertEqual(self.params(0)["WFTextActionText"], "")
        uuid_like = re.compile(r"^[0-9A-F]{8}(-[0-9A-F]{4}){3}-[0-9A-F]{12}$")
        self.assertEqual([v for v in _strings(self.plist) if re.fullmatch(r"[A-Za-z0-9_-]{30,}", v) and not uuid_like.match(v) and not v.startswith("WF")], [])
        self.assertEqual(self.params(4)["WFNotificationActionBody"]["Value"]["attachmentsByRange"]["{0, 1}"]["OutputUUID"], self.params(3)["UUID"])


if __name__ == "__main__":
    unittest.main()
