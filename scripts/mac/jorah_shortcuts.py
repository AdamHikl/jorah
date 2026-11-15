"""Builds Jorah's iPhone shortcuts, unsigned (docs/runbooks/phone.md: Ask Jorah, Share to Jorah).

    python3 -I scripts/mac/jorah_shortcuts.py ask /tmp/ask-jorah.shortcut
    python3 -I scripts/mac/jorah_shortcuts.py share /tmp/share-to-jorah.shortcut
    shortcuts sign --mode people-who-know-me --input /tmp/ask-jorah.shortcut --output "Ask Jorah.shortcut"

A signed file carries Adam's iCloud signature: keep it out of the repo. AirDrop it to the phone,
add it, then open it and paste the phone's token (only the token) into the first step, the empty
Text box. There is no token in the file. An import question for the token was tried on 2026-11-15
and iOS's Add Shortcut button then did nothing, so the box is filled by hand instead.
"""

import argparse
import plistlib
import sys
import uuid

BASE = "https://rocket.tail1574a5.ts.net:43213"
URL = f"{BASE}/ask"
SHARE_URL = f"{BASE}/share"
SLOT = "￼"  # where a variable sits inside a text field


def _id():
    return str(uuid.uuid4()).upper()


def _ref(uid, name):
    return {"OutputName": name, "OutputUUID": uid, "Type": "ActionOutput"}


def _text(s, attachments=None):
    value = {"string": s}
    if attachments:
        value["attachmentsByRange"] = attachments
    return {"Value": value, "WFSerializationType": "WFTextTokenString"}


def _fields(items):
    return {"Value": {"WFDictionaryFieldValueItems": items}, "WFSerializationType": "WFDictionaryFieldValue"}


def _field(kind, key, value):
    return {"WFItemType": kind, "WFKey": _text(key), "WFValue": value}  # kind 0 text, 3 number


def _shortcut(actions, types=(), inputs=(), no_input=None):
    plist = {
        "WFWorkflowClientVersion": "2607.0.2",
        "WFWorkflowMinimumClientVersion": 900,
        "WFWorkflowMinimumClientVersionString": "900",
        "WFWorkflowIcon": {"WFWorkflowIconStartColor": 463140863, "WFWorkflowIconGlyphNumber": 59446},
        "WFWorkflowImportQuestions": [],
        "WFWorkflowTypes": list(types),
        "WFWorkflowInputContentItemClasses": list(inputs),
        "WFWorkflowHasShortcutInputVariables": bool(inputs),
        "WFQuickActionSurfaces": [],
        "WFWorkflowActions": actions,
    }
    if no_input:
        plist["WFWorkflowNoInputBehavior"] = no_input
    return plist


def build_share(url=SHARE_URL):
    """Share sheet: the shared text (or the clipboard when run with nothing shared), an optional note,
    sent to Jorah's Shared chat; a notification says whether it arrived."""
    token, note, contents, answer = _id(), _id(), _id(), _id()
    shared = {"Type": "ExtensionInput"}
    actions = [
        {"WFWorkflowActionIdentifier": "is.workflow.actions.gettext",
         "WFWorkflowActionParameters": {"UUID": token, "WFTextActionText": ""}},
        {"WFWorkflowActionIdentifier": "is.workflow.actions.ask",
         "WFWorkflowActionParameters": {"UUID": note, "WFAskActionPrompt": "Note for Jorah (optional)", "WFInputType": "Text",
                                        "WFAskActionDefaultAnswer": ""}},
        {"WFWorkflowActionIdentifier": "is.workflow.actions.downloadurl",
         "WFWorkflowActionParameters": {
             "UUID": contents, "WFURL": url, "WFHTTPMethod": "POST", "ShowHeaders": True,
             "WFHTTPHeaders": _fields([_field(0, "Authorization", _text(f"Bearer {SLOT}", {"{7, 1}": _ref(token, "Text")}))]),
             "WFHTTPBodyType": "JSON",
             "WFJSONValues": _fields([
                 _field(3, "v", _text("1")),
                 _field(0, "text", _text(SLOT, {"{0, 1}": shared})),
                 _field(0, "note", _text(SLOT, {"{0, 1}": _ref(note, "Provided Input")})),
                 _field(0, "source", _text("other")),
             ]),
         }},
        {"WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
         "WFWorkflowActionParameters": {"UUID": answer, "WFGetDictionaryValueType": "Value", "WFDictionaryKey": "say",
                                        "WFInput": {"Value": _ref(contents, "Contents of URL"), "WFSerializationType": "WFTextTokenAttachment"}}},
        {"WFWorkflowActionIdentifier": "is.workflow.actions.notification",
         "WFWorkflowActionParameters": {"UUID": _id(), "WFNotificationActionTitle": "Jorah",
                                        "WFNotificationActionBody": _text(SLOT, {"{0, 1}": _ref(answer, "Dictionary Value")})}},
    ]
    return _shortcut(actions, types=["ActionExtension"],
                     inputs=["WFStringContentItem", "WFRichTextContentItem", "WFURLContentItem"],
                     no_input={"Name": "WFWorkflowNoInputBehaviorGetClipboard", "Parameters": {}})


def build(url=URL, language="en-US"):
    token, dictated, contents, answer = _id(), _id(), _id(), _id()
    actions = [
        {"WFWorkflowActionIdentifier": "is.workflow.actions.gettext",
         "WFWorkflowActionParameters": {"UUID": token, "WFTextActionText": ""}},
        {"WFWorkflowActionIdentifier": "is.workflow.actions.dictatetext",
         "WFWorkflowActionParameters": {"UUID": dictated, "WFSpeechLanguage": language, "WFDictateTextStopListening": "After Pause"}},
        {"WFWorkflowActionIdentifier": "is.workflow.actions.downloadurl",
         "WFWorkflowActionParameters": {
             "UUID": contents, "WFURL": url, "WFHTTPMethod": "POST", "ShowHeaders": True,
             "WFHTTPHeaders": _fields([_field(0, "Authorization", _text(f"Bearer {SLOT}", {"{7, 1}": _ref(token, "Text")}))]),
             "WFHTTPBodyType": "JSON",
             "WFJSONValues": _fields([_field(3, "v", _text("1")), _field(0, "text", _text(SLOT, {"{0, 1}": _ref(dictated, "Dictated Text")}))]),
         }},
        {"WFWorkflowActionIdentifier": "is.workflow.actions.getvalueforkey",
         "WFWorkflowActionParameters": {"UUID": answer, "WFGetDictionaryValueType": "Value", "WFDictionaryKey": "say",
                                        "WFInput": {"Value": _ref(contents, "Contents of URL"), "WFSerializationType": "WFTextTokenAttachment"}}},
        {"WFWorkflowActionIdentifier": "is.workflow.actions.speaktext",
         "WFWorkflowActionParameters": {"UUID": _id(), "WFText": _text(SLOT, {"{0, 1}": _ref(answer, "Dictionary Value")}), "WFSpeakTextWait": True}},
    ]
    return _shortcut(actions)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("kind", choices=("ask", "share"))
    p.add_argument("output")
    p.add_argument("--base", default=BASE, help="the jorah-phone address, no path")
    p.add_argument("--language", default="en-US", help="Ask Jorah's dictation language; iOS may ignore it")
    args = p.parse_args(argv)
    base = args.base.rstrip("/")
    plist = build(f"{base}/ask", args.language) if args.kind == "ask" else build_share(f"{base}/share")
    with open(args.output, "wb") as handle:
        plistlib.dump(plist, handle, fmt=plistlib.FMT_BINARY)
    name = "Ask Jorah" if args.kind == "ask" else "Share to Jorah"
    print(f"Unsigned shortcut written to {args.output}. Sign it with: shortcuts sign --input {args.output} --output '{name}.shortcut'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
