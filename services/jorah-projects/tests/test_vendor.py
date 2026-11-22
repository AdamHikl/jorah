"""Vendor files for a project (issue #17): the runner downloads only what passes every check."""

import json
import socket
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from jorah_projects import vendor

PDF = b"%PDF-1.7\n" + b"x" * 200
STEP = b"ISO-10303-21;\nHEADER;\n"
STL_BIN = b"\0" * 80 + (2).to_bytes(4, "little") + b"\0" * 100
URL = "https://datasheets.raspberrypi.com/camera/camera-module-3-product-brief.pdf"


def project(web=True):
    return SimpleNamespace(name="arm", state_dir="project", web=web)


class Fetcher:
    def __init__(self, answers):
        self.answers, self.calls = answers, []

    def __call__(self, url, cap):
        self.calls.append(url)
        data, ctype = self.answers[url]
        if len(data) > cap:
            raise vendor.Refused("over the limit")
        return url, data, ctype


class VendorTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="jorah-vendor-"))
        self.own = Path(tempfile.mkdtemp(prefix="jorah-vendor-state-"))
        (self.root / "project" / "vendor" / "requests").mkdir(parents=True)

    def request(self, name, **fields):
        body = {"v": 1, "url": URL, "name": "cam3.pdf", "kind": "pdf", "why": "lens position and board size", **fields}
        (self.root / "project" / "vendor" / "requests" / name).write_text(json.dumps(body))

    def test_a_pdf_is_saved_with_hash_text_manifest_and_gitignore(self):
        self.request("cam.json")
        text = lambda path, out: (Path(out[0]) / out[1]).write_bytes(b"text") or "cam3.pdf.txt"
        got = vendor.collect(project(), self.root, self.own, get=Fetcher({URL: (PDF, "application/pdf")}), text=text, now=lambda: "2026-11-22T10:00:00+00:00")
        self.assertEqual([f["name"] for f in got["fetched"]], ["cam3.pdf"])
        saved = self.root / "project" / "vendor" / "cam3.pdf"
        self.assertEqual(saved.read_bytes(), PDF)
        self.assertEqual(saved.stat().st_mode & 0o777, 0o644)
        manifest = json.loads((self.root / "project" / "vendor" / "MANIFEST.json").read_text())
        self.assertEqual(manifest["cam3.pdf"]["provenance"], "unverified")
        self.assertEqual(manifest["cam3.pdf"]["text"], "cam3.pdf.txt")
        self.assertEqual(len(manifest["cam3.pdf"]["sha256"]), 64)
        self.assertIn("!MANIFEST.json", (self.root / "project" / "vendor" / ".gitignore").read_text())
        self.assertFalse((self.root / "project" / "vendor" / "requests" / "cam.json").exists())
        self.assertTrue((self.own / "vendor.json").exists())

    def test_no_web_no_download(self):
        self.request("cam.json")
        fetch = Fetcher({URL: (PDF, "application/pdf")})
        got = vendor.collect(project(web=False), self.root, self.own, get=fetch)
        self.assertEqual(fetch.calls, [])
        self.assertIn("no web research", got["refused"][0]["why"])

    def test_wrong_bytes_html_and_bad_requests_are_refused_and_moved_aside(self):
        self.request("html.json")
        self.request("step.json", url="https://example.com/m.step", name="m.step", kind="step")
        self.request("ext.json", name="cam3.exe")
        self.request("http.json", url="http://example.com/a.pdf", name="a.pdf")
        self.request("cred.json", url="https://example.com/a.pdf?token=abc", name="b.pdf")
        fetch = Fetcher({URL: (b"<!DOCTYPE html><html>", "text/html"), "https://example.com/m.step": (PDF, "application/octet-stream")})
        got = vendor.collect(project(), self.root, self.own, get=fetch, text=lambda *a: None)
        self.assertEqual(got["fetched"], [])
        self.assertEqual(len(got["refused"]), 5)
        bad = self.root / "project" / "vendor" / "requests" / "bad"
        self.assertTrue((bad / "html.json.why.txt").exists())
        self.assertFalse(list((self.root / "project" / "vendor").glob("*.pdf")))

    def test_magic_bytes(self):
        self.assertTrue(vendor.is_kind("pdf", PDF))
        self.assertTrue(vendor.is_kind("step", STEP))
        self.assertTrue(vendor.is_kind("stl", STL_BIN))
        self.assertTrue(vendor.is_kind("stl", b"solid arm\n facet normal 0 0 1\n"))
        self.assertTrue(vendor.is_kind("kicad_mod", b"(footprint \"R_0603\""))
        self.assertTrue(vendor.is_kind("kicad_sym", b"(kicad_symbol_lib (version 2023)"))
        self.assertFalse(vendor.is_kind("stl", b"PK\x03\x04zip"))
        self.assertFalse(vendor.is_kind("pdf", b"<html>%PDF-"))
        self.assertFalse(vendor.is_kind("stl", b"\0" * 80 + (3).to_bytes(4, "little") + b"\0" * 100))

    def test_urls_and_addresses(self):
        for bad in ["http://a.example/x.pdf", "https://user:pw@a.example/x", "https://a.example:8443/x", "https://localhost/x",
                    "https://box.tail1234.ts.net/x", "https://127.0.0.1/x", "https://a.example/x?api_key=1", "https://" + "a" * 400]:
            with self.assertRaises(vendor.Refused, msg=bad):
                vendor.check_url(bad)
        vendor.check_url(URL)
        res = lambda addrs: (lambda host, port, type=None: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (a, 443)) for a in addrs])
        self.assertEqual(vendor.public_address("a.example", res(["93.184.215.14"])), "93.184.215.14")
        for addrs in (["10.0.0.5"], ["93.184.215.14", "192.168.1.2"], ["100.100.1.1"], ["169.254.169.254"], ["::1"]):
            with self.assertRaises(vendor.Refused, msg=addrs):
                vendor.public_address("a.example", res(addrs))

    def test_redirects_are_checked_each_time(self):
        class Conn:
            def __init__(self, host, address):
                self.host = host

            def request(self, *a, **k):
                pass

            def getresponse(self):
                return SimpleNamespace(status=302, getheader=lambda k: "https://169.254.169.254/latest" if k == "Location" else None, read=lambda n: b"")

            def close(self):
                pass

        resolve = lambda host, port, type=None: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.215.14", 443))]
        with self.assertRaises(vendor.Refused):
            vendor.https_get(URL, 1000, resolve=resolve, connection=Conn)

    def test_at_most_ten_per_run(self):
        for i in range(12):
            self.request(f"r{i:02}.json", name=f"d{i:02}.pdf")
        got = vendor.collect(project(), self.root, self.own, get=Fetcher({URL: (PDF, "application/pdf")}), text=lambda *a: None)
        self.assertEqual(len(got["fetched"]), 10)
        self.assertEqual(sum("next run" in r["why"] for r in got["refused"]), 2)


if __name__ == "__main__":
    unittest.main()
