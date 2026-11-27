import Foundation
import XCTest
@testable import HUDCore

final class SentFilesTests: XCTestCase {
    /// The content array of an assistant message, shaped as OpenClaw 2026.11.6 sends it.
    private func content(_ json: String) -> Any? {
        try? JSONSerialization.jsonObject(with: Data(json.utf8))
    }

    func testReadsADocumentAttachment() {
        let files = SentFiles.parse(content: content("""
        [{"type":"text","text":"Here is the report."},
         {"type":"attachment","attachment":{"artifactId":"att-1","url":"/api/chat/media/outgoing/agent%3Amain%3Amain/att-1/full",
          "kind":"document","label":"report.pdf","mimeType":"application/pdf","sizeBytes":48213}}]
        """))
        XCTAssertEqual(files, [SentFile(artifactId: "att-1", kind: .document, name: "report.pdf",
                                        mimeType: "application/pdf", sizeBytes: 48213)])
        XCTAssertEqual(files.first?.viewer, .pdf)
    }

    func testReadsAPictureBlockAndUsesItsAltAsName() {
        let files = SentFiles.parse(content: content("""
        [{"type":"image","artifactId":"img-9","url":"/x","openUrl":"/y","alt":"plot","mimeType":"image/png","width":800,"height":600,"sizeBytes":1200.0}]
        """))
        XCTAssertEqual(files.count, 1)
        XCTAssertEqual(files[0].kind, .image)
        XCTAssertEqual(files[0].name, "plot.png")
        XCTAssertEqual(files[0].sizeBytes, 1200)
        XCTAssertEqual(files[0].viewer, .image)
    }

    func testSkipsBlocksWithoutAnArtifactAndDuplicates() {
        let files = SentFiles.parse(content: content("""
        [{"type":"image","data":"aGVsbG8=","mimeType":"image/png"},
         {"type":"attachment","attachment":{"label":"no-id.pdf"}},
         {"type":"audio","artifactId":"a1","fileName":"note.mp3","mimeType":"audio/mpeg"},
         {"type":"audio","artifactId":"a1","fileName":"note.mp3","mimeType":"audio/mpeg"}]
        """))
        XCTAssertEqual(files.map(\.artifactId), ["a1"])
        XCTAssertEqual(files[0].viewer, .quickLook)
        XCTAssertNil(files[0].sizeBytes, "a missing size stays unknown, not 0")
    }

    func testTextOnlyOrStringContentHasNoFiles() {
        XCTAssertEqual(SentFiles.parse(content: "just text"), [])
        XCTAssertEqual(SentFiles.parse(content: nil), [])
        XCTAssertEqual(SentFiles.parse(content: content(#"[{"type":"text","text":"hi"}]"#)), [])
    }

    func testFileNamesAreMadeSafe() {
        XCTAssertEqual(SentFiles.safeFileName("../../etc/passwd", mimeType: nil, kind: .document), "passwd")
        XCTAssertEqual(SentFiles.safeFileName("/home/jorah/workspace/files/notes.md", mimeType: "text/markdown", kind: .document), "notes.md")
        XCTAssertEqual(SentFiles.safeFileName("...hidden", mimeType: "text/plain", kind: .document), "hidden.txt")
        XCTAssertEqual(SentFiles.safeFileName("a\u{0}b\nc.txt", mimeType: nil, kind: .document), "abc.txt")
        XCTAssertEqual(SentFiles.safeFileName(nil, mimeType: "image/jpeg", kind: .image), "picture.jpg")
        XCTAssertEqual(SentFiles.safeFileName("  ", mimeType: nil, kind: .document), "file")
        let long = SentFiles.safeFileName(String(repeating: "x", count: 300) + ".pdf", mimeType: nil, kind: .document)
        XCTAssertEqual(long.count, 120)
        XCTAssertTrue(long.hasSuffix(".pdf"))
    }

    func testViewerChoice() {
        XCTAssertEqual(SentFiles.viewer(mimeType: "text/markdown", name: "a", kind: .document), .markdown)
        XCTAssertEqual(SentFiles.viewer(mimeType: nil, name: "plan.md", kind: .document), .markdown)
        XCTAssertEqual(SentFiles.viewer(mimeType: "text/csv", name: "a.csv", kind: .document), .text)
        XCTAssertEqual(SentFiles.viewer(mimeType: "application/json", name: "a", kind: .document), .text)
        XCTAssertEqual(SentFiles.viewer(mimeType: "text/html", name: "a.html", kind: .document), .text)
        XCTAssertEqual(SentFiles.viewer(mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                        name: "a.docx", kind: .document), .quickLook)
        XCTAssertEqual(SentFiles.viewer(mimeType: "application/zip", name: "a.zip", kind: .document), .quickLook)
    }

    func testUniqueNames() {
        let taken: Set = ["report.pdf", "report 2.pdf", "README"]
        XCTAssertEqual(SentFiles.uniqueName("report.pdf") { taken.contains($0) }, "report 3.pdf")
        XCTAssertEqual(SentFiles.uniqueName("README") { taken.contains($0) }, "README 2")
        XCTAssertEqual(SentFiles.uniqueName("new.md") { taken.contains($0) }, "new.md")
    }

    func testSizeLabelIsUnknownWithoutASize() {
        XCTAssertNil(SentFiles.sizeLabel(nil))
        XCTAssertNotNil(SentFiles.sizeLabel(0))
    }

    func testDownloadURLStaysOnTheGatewayOrigin() {
        let origin = URL(string: "https://rocket.example.ts.net")!
        XCTAssertEqual(SentFiles.downloadURL("/api/chat/media/outgoing/s/a/full?mediaTicket=t", origin: origin)?.absoluteString,
                       "https://rocket.example.ts.net/api/chat/media/outgoing/s/a/full?mediaTicket=t")
        XCTAssertEqual(SentFiles.downloadURL("https://rocket.example.ts.net/x", origin: origin)?.absoluteString,
                       "https://rocket.example.ts.net/x")
        XCTAssertNil(SentFiles.downloadURL("https://evil.example.com/x", origin: origin))
        XCTAssertNil(SentFiles.downloadURL("//evil.example.com/x", origin: origin))
        XCTAssertNil(SentFiles.downloadURL("http://rocket.example.ts.net/x", origin: origin))
        XCTAssertNil(SentFiles.downloadURL("file:///etc/passwd", origin: origin))
        let local = URL(string: "http://127.0.0.1:43181")!
        XCTAssertEqual(SentFiles.downloadURL("/a", origin: local)?.absoluteString, "http://127.0.0.1:43181/a")
    }
}

final class MarkdownBlocksTests: XCTestCase {
    func testHeadingsParagraphsAndLists() {
        let blocks = MarkdownBlocks.parse("""
        # Plan

        First line
        continues here.

        - one
          - nested
        - [x] done
        2. second
        ---
        > quoted
        > more
        """)
        XCTAssertEqual(blocks, [
            .heading(level: 1, text: "Plan"),
            .paragraph("First line continues here."),
            .item(marker: "•", depth: 0, text: "one"),
            .item(marker: "•", depth: 1, text: "nested"),
            .item(marker: "☑", depth: 0, text: "done"),
            .item(marker: "2.", depth: 0, text: "second"),
            .rule,
            .quote("quoted\nmore"),
        ])
    }

    func testCodeFencesKeepTheirText() {
        let blocks = MarkdownBlocks.parse("```swift\nlet a = 1\n# not a heading\n```\nafter")
        XCTAssertEqual(blocks, [.code(language: "swift", text: "let a = 1\n# not a heading"), .paragraph("after")])
    }

    func testAnUnclosedFenceStillShowsItsText() {
        XCTAssertEqual(MarkdownBlocks.parse("```\nkept"), [.code(language: nil, text: "kept")])
    }

    func testTablesAndNonHeadings() {
        let blocks = MarkdownBlocks.parse("| a | b |\n|---|---|\n| 1 | 2 |\n#hashtag")
        XCTAssertEqual(blocks, [.table("| a | b |\n|---|---|\n| 1 | 2 |"), .paragraph("#hashtag")])
    }
}
