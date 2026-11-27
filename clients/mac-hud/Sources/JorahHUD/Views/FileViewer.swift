import AppKit
import HUDCore
import PDFKit
import Quartz
import SwiftUI

/// A card for a file Jorah sent, under his reply. Click opens it in a HUD window; the context menu
/// also saves it. A picture shows a thumbnail once fetched, otherwise an icon.
struct SentFileCard: View {
    let file: SentFile
    @Environment(HUDModel.self) private var model
    @Environment(\.openWindow) private var openWindow
    @State private var note: String?

    var body: some View {
        let ref = model.fileRef(file)
        VStack(alignment: .leading, spacing: 2) {
            Button {
                if let ref { openWindow(id: "file", value: ref) }
            } label: {
                HStack(spacing: 8) {
                    if let ref, let thumbnail = model.fileThumbnails[ref.key] {
                        Image(nsImage: thumbnail)
                            .resizable()
                            .aspectRatio(contentMode: .fill)
                            .frame(width: 44, height: 44)
                            .clipped()
                    } else {
                        Image(systemName: Self.icon(file))
                            .font(.system(size: 18))
                            .foregroundStyle(Theme.accent)
                            .frame(width: 44, height: 44)
                    }
                    VStack(alignment: .leading, spacing: 2) {
                        Text(file.name)
                            .font(.system(size: 12, weight: .medium))
                            .foregroundStyle(Theme.text)
                            .lineLimit(1)
                            .truncationMode(.middle)
                        Text(Self.detail(file)).font(Theme.label(9)).foregroundStyle(Theme.dim)
                    }
                    Spacer(minLength: 4)
                    Image(systemName: "arrow.up.forward.app").foregroundStyle(Theme.dim)
                }
                .padding(6)
                .frame(maxWidth: 340, alignment: .leading)
                .background(Theme.surface)
                .overlay(Rectangle().stroke(Theme.stroke, lineWidth: 0.5))
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .disabled(ref == nil)
            .help("Open \(file.name) in the HUD")
            .contextMenu {
                if let ref {
                    Button("Open") { openWindow(id: "file", value: ref) }
                    Button("Save to Downloads") { save(ref, choose: false) }
                    Button("Save As…") { save(ref, choose: true) }
                }
            }
            .accessibilityLabel("File from Jorah: \(file.name), \(Self.detail(file))")
            if let note {
                Text(note).font(.system(size: 11)).foregroundStyle(Theme.dim).textSelection(.enabled)
            }
        }
        .task(id: ref?.key) {
            if let ref { await model.loadThumbnail(ref) }
        }
    }

    private func save(_ ref: FileRef, choose: Bool) {
        note = "Fetching…"
        Task {
            do {
                let target = choose ? try await model.saveAs(ref) : try await model.saveToDownloads(ref)
                note = target.map { "Saved to \($0.path(percentEncoded: false))" }
            } catch {
                note = "Not saved: \(error.localizedDescription)"
            }
        }
    }

    static func icon(_ file: SentFile) -> String {
        switch file.kind {
        case .image: return "photo"
        case .audio: return "waveform"
        case .video: return "film"
        case .document: break
        }
        switch file.viewer {
        case .pdf: return "doc.richtext"
        case .markdown: return "doc.text"
        case .text: return "doc.plaintext"
        default: return (file.name as NSString).pathExtension.lowercased() == "zip" ? "doc.zipper" : "doc"
        }
    }

    /// "PDF · 48 KB", or "PDF · size unknown" when the Gateway didn't say.
    static func detail(_ file: SentFile) -> String {
        let ext = (file.name as NSString).pathExtension.uppercased()
        let type = ext.isEmpty ? file.kind.rawValue.uppercased() : ext
        return "\(type) · \(SentFiles.sizeLabel(file.sizeBytes) ?? "size unknown")"
    }
}

/// The window a file opens in: pictures (pinch to zoom), PDFs, Markdown, text, CSV and JSON drawn by
/// the HUD; Office files, archives, sound and video through Quick Look. Save buttons on top.
struct FileViewer: View {
    let ref: FileRef
    @Environment(HUDModel.self) private var model
    @State private var state: LoadState = .loading
    @State private var note: String?
    @State private var saving = false

    enum LoadState {
        case loading
        case failed(String)
        case image(NSImage)
        case pdf(PDFDocument)
        case markdown([MarkdownBlock], clipped: Bool)
        case text(String, clipped: Bool)
        case quickLook(URL)
    }

    /// Text past this is left out of the window (the saved file has all of it).
    private static let textLimit = 1_000_000

    var body: some View {
        VStack(spacing: 0) {
            header
            Rectangle().fill(Theme.stroke).frame(height: 0.5)
            content.frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .background(Theme.background)
        .preferredColorScheme(.dark)
        .navigationTitle(ref.file.name)
        .task(id: ref) { await load() }
    }

    private var header: some View {
        HStack(spacing: 10) {
            Image(systemName: SentFileCard.icon(ref.file)).font(.system(size: 16)).foregroundStyle(Theme.accent)
            VStack(alignment: .leading, spacing: 2) {
                Text(ref.file.name).font(.system(size: 13, weight: .semibold)).foregroundStyle(Theme.text)
                    .lineLimit(1).truncationMode(.middle)
                Text("FROM JORAH · " + SentFileCard.detail(ref.file)).font(Theme.label(9)).tracking(1.0).foregroundStyle(Theme.dim)
            }
            Spacer(minLength: 8)
            if let note {
                Text(note).font(.system(size: 11)).foregroundStyle(Theme.dim).lineLimit(2).textSelection(.enabled)
            }
            Button("Save to Downloads") { save(choose: false) }.disabled(saving)
            Button("Save As…") { save(choose: true) }.disabled(saving)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
    }

    @ViewBuilder
    private var content: some View {
        switch state {
        case .loading:
            VStack(spacing: 8) {
                ProgressView().controlSize(.small)
                Text("Fetching from the PC…").font(.system(size: 12)).foregroundStyle(Theme.dim)
            }
        case .failed(let reason):
            VStack(spacing: 10) {
                Text("Couldn't open \(ref.file.name)").font(.system(size: 13, weight: .semibold)).foregroundStyle(Theme.text)
                Text(reason).font(.system(size: 12)).foregroundStyle(Theme.dim).multilineTextAlignment(.center)
                    .textSelection(.enabled)
                Button("Try again") { Task { await load() } }
            }
            .padding(24)
        case .image(let image):
            ZoomableImage(image: image)
        case .pdf(let document):
            PDFViewer(document: document)
        case .markdown(let blocks, let clipped):
            ScrollView {
                MarkdownDocument(blocks: blocks)
                    .padding(24)
                    .frame(maxWidth: 820, alignment: .leading)
                    .frame(maxWidth: .infinity)
                if clipped { clippedNote }
            }
        case .text(let text, let clipped):
            ScrollView([.vertical, .horizontal]) {
                VStack(alignment: .leading, spacing: 8) {
                    Text(text).font(Theme.mono(12)).foregroundStyle(Theme.text).textSelection(.enabled)
                    if clipped { clippedNote }
                }
                .padding(16)
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        case .quickLook(let url):
            QuickLookPreview(url: url)
        }
    }

    private var clippedNote: some View {
        Text("Only the first megabyte is shown here. Save the file to read all of it.")
            .font(.system(size: 11)).foregroundStyle(Theme.amber).padding(16)
    }

    private func load() async {
        state = .loading
        do {
            let url = try await model.localCopy(of: ref)
            switch ref.file.viewer {
            case .image:
                guard let image = NSImage(contentsOf: url) else { throw FileError(message: "It isn't a picture this Mac can read.") }
                state = .image(image)
            case .pdf:
                guard let document = PDFDocument(url: url) else { throw FileError(message: "It isn't a PDF this Mac can read.") }
                state = .pdf(document)
            case .markdown:
                let (text, clipped) = try Self.readText(url)
                state = .markdown(MarkdownBlocks.parse(text), clipped: clipped)
            case .text:
                let (text, clipped) = try Self.readText(url)
                state = .text(text, clipped: clipped)
            case .quickLook:
                state = .quickLook(url)
            }
        } catch {
            state = .failed(error.localizedDescription)
        }
    }

    private static func readText(_ url: URL) throws -> (String, Bool) {
        let handle = try FileHandle(forReadingFrom: url)
        defer { try? handle.close() }
        let data = try handle.read(upToCount: textLimit + 1) ?? Data()
        let clipped = data.count > textLimit
        return (String(decoding: clipped ? data.prefix(textLimit) : data, as: UTF8.self), clipped)
    }

    private func save(choose: Bool) {
        saving = true
        note = "Saving…"
        Task {
            defer { saving = false }
            do {
                let target = choose ? try await model.saveAs(ref) : try await model.saveToDownloads(ref)
                note = target.map { "Saved to \($0.path(percentEncoded: false))" }
            } catch {
                note = "Not saved: \(error.localizedDescription)"
            }
        }
    }
}

/// Markdown blocks drawn with SwiftUI. Inline marks come from `AttributedString(markdown:)`; only
/// web and mail links stay clickable.
struct MarkdownDocument: View {
    let blocks: [MarkdownBlock]

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            ForEach(blocks.indices, id: \.self) { index in
                block(blocks[index])
            }
        }
        .foregroundStyle(Theme.text)
        .textSelection(.enabled)
    }

    @ViewBuilder
    private func block(_ block: MarkdownBlock) -> some View {
        switch block {
        case .heading(let level, let text):
            Text(Self.inline(text))
                .font(.system(size: [24, 20, 17, 15, 14, 13][min(max(level, 1), 6) - 1], weight: .semibold))
                .padding(.top, level <= 2 ? 8 : 2)
        case .paragraph(let text):
            Text(Self.inline(text)).font(.system(size: 14)).lineSpacing(3)
        case .item(let marker, let depth, let text):
            HStack(alignment: .firstTextBaseline, spacing: 6) {
                Text(marker).foregroundStyle(Theme.dim)
                Text(Self.inline(text))
            }
            .font(.system(size: 14))
            .padding(.leading, CGFloat(depth) * 18)
        case .quote(let text):
            Text(Self.inline(text))
                .font(.system(size: 14))
                .foregroundStyle(Theme.dim)
                .padding(.leading, 12)
                .overlay(alignment: .leading) { Rectangle().fill(Theme.stroke).frame(width: 2) }
        case .code(_, let text), .table(let text):
            ScrollView(.horizontal) {
                Text(text).font(Theme.mono(12)).padding(10)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Theme.surface)
            .overlay(Rectangle().stroke(Theme.stroke, lineWidth: 0.5))
        case .rule:
            Rectangle().fill(Theme.stroke).frame(height: 0.5).padding(.vertical, 4)
        }
    }

    static func inline(_ text: String) -> AttributedString {
        let options = AttributedString.MarkdownParsingOptions(interpretedSyntax: .inlineOnlyPreservingWhitespace)
        var out = (try? AttributedString(markdown: text, options: options)) ?? AttributedString(text)
        for run in out.runs {
            guard let link = run.link else { continue }
            if !["http", "https", "mailto"].contains(link.scheme?.lowercased() ?? "") { out[run.range].link = nil }
        }
        return out
    }
}

/// A picture in a scroll view: it opens fitted to the window; pinch or ⌘-scroll to zoom.
struct ZoomableImage: NSViewRepresentable {
    let image: NSImage

    func makeNSView(context: Context) -> NSScrollView {
        let scroll = NSScrollView()
        scroll.contentView = CenteringClipView()
        scroll.allowsMagnification = true
        scroll.minMagnification = 0.05
        scroll.maxMagnification = 8
        scroll.hasVerticalScroller = true
        scroll.hasHorizontalScroller = true
        scroll.autohidesScrollers = true
        scroll.drawsBackground = true
        scroll.backgroundColor = NSColor(white: 0.04, alpha: 1)
        let view = NSImageView(image: image)
        view.imageScaling = .scaleProportionallyUpOrDown
        view.frame = NSRect(origin: .zero, size: image.size)
        scroll.documentView = view
        DispatchQueue.main.async {
            scroll.magnify(toFit: view.frame)
            if scroll.magnification > 1 { scroll.magnification = 1 }
        }
        return scroll
    }

    func updateNSView(_ scroll: NSScrollView, context: Context) {}
}

/// Keeps a picture smaller than the window in the middle instead of the bottom-left corner.
final class CenteringClipView: NSClipView {
    override func constrainBoundsRect(_ proposedBounds: NSRect) -> NSRect {
        var rect = super.constrainBoundsRect(proposedBounds)
        guard let document = documentView else { return rect }
        if rect.width > document.frame.width { rect.origin.x = (document.frame.width - rect.width) / 2 }
        if rect.height > document.frame.height { rect.origin.y = (document.frame.height - rect.height) / 2 }
        return rect
    }
}

struct PDFViewer: NSViewRepresentable {
    let document: PDFDocument

    func makeNSView(context: Context) -> PDFView {
        let view = PDFView()
        view.autoScales = true
        view.displayMode = .singlePageContinuous
        view.document = document
        return view
    }

    func updateNSView(_ view: PDFView, context: Context) {}
}

/// Office files, archives, sound and video: whatever Quick Look can show on this Mac.
struct QuickLookPreview: NSViewRepresentable {
    let url: URL

    func makeNSView(context: Context) -> NSView {
        guard let view = QLPreviewView(frame: .zero, style: .normal) else {
            let label = NSTextField(labelWithString: "Quick Look isn't available. Save the file to open it.")
            label.textColor = .secondaryLabelColor
            return label
        }
        view.previewItem = url as NSURL
        return view
    }

    func updateNSView(_ view: NSView, context: Context) {}

    static func dismantleNSView(_ view: NSView, coordinator: ()) {
        (view as? QLPreviewView)?.close()
    }
}
