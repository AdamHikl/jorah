"""Builds the Ask Jorah shortcut for the iPhone (docs/runbooks/phone.md, A4), unsigned.

    python3 -I scripts/mac/ask_jorah_shortcut.py /tmp/ask-jorah.shortcut
    shortcuts sign --mode people-who-know-me --input /tmp/ask-jorah.shortcut --output "Ask Jorah.shortcut"

The signed file carries Adam's iCloud signature: keep it out of the repo. AirDrop it to the phone,
add it, then open it and paste the phone's token (only the token) into the first step, the empty
Text box. There is no token in the file. An import question for the token was tried on 2026-11-15
and iOS's Add Shortcut button then did nothing, so the box is filled by hand instead.
"""

import argparse
import plistlib
import sys
import uuid

URL = "https://rocket.tail1574a5.ts.net:43213/ask"
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
    return {
        "WFWorkflowClientVersion": "2607.0.2",
        "WFWorkflowMinimumClientVersion": 900,
        "WFWorkflowMinimumClientVersionString": "900",
        "WFWorkflowIcon": {"WFWorkflowIconStartColor": 463140863, "WFWorkflowIconGlyphNumber": 59446},
        "WFWorkflowImportQuestions": [],
        "WFWorkflowTypes": [],
        "WFWorkflowInputContentItemClasses": [],
        "WFWorkflowHasShortcutInputVariables": False,
        "WFQuickActionSurfaces": [],
        "WFWorkflowActions": actions,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("output")
    p.add_argument("--url", default=URL)
    p.add_argument("--language", default="en-US", help="Dictate Text's language; iOS may ignore it")
    args = p.parse_args(argv)
    with open(args.output, "wb") as handle:
        plistlib.dump(build(args.url, args.language), handle, fmt=plistlib.FMT_BINARY)
    print(f"Unsigned shortcut written to {args.output}. Sign it with: shortcuts sign --input {args.output} --output 'Ask Jorah.shortcut'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
