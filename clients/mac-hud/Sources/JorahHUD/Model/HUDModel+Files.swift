import AppKit
import Foundation
import HUDCore
import ImageIO

/// A file Jorah sent, with the conversation it came in: what a file window opens.
struct FileRef: Codable, Hashable {
    let sessionKey: String
    let file: SentFile
    var key: String { sessionKey + "|" + file.artifactId }
}

struct FileError: LocalizedError {
    let message: String
    var errorDescription: String? { message }
}

/// Files Jorah sends with a `MEDIA:` line (OpenClaw keeps each as a managed artifact of the
/// conversation). The HUD fetches one with `artifacts.download`, which answers with the bytes or
/// with a link on the Gateway's own origin that carries a ticket of about five minutes, so each
/// fetch asks afresh. Copies live in a temporary folder for this run of the HUD; saving puts a copy
/// where Adam chooses, marked as downloaded so macOS checks it like any other download.
extension HUDModel {
    func fileRef(_ file: SentFile) -> FileRef? {
        currentSessionKey.map { FileRef(sessionKey: $0, file: file) }
    }

    /// A local copy of the file, fetched once per run of the HUD. Callers asking at once share one fetch.
    func localCopy(of ref: FileRef) async throws -> URL {
        if let copy = fileCopies[ref.key], FileManager.default.fileExists(atPath: copy.path) { return copy }
        if let running = fileDownloads[ref.key] { return try await running.value }
        let task = Task { try await self.fetch(ref) }
        fileDownloads[ref.key] = task
        defer { fileDownloads[ref.key] = nil }
        let copy = try await task.value
        fileCopies[ref.key] = copy
        return copy
    }

    private func fetch(_ ref: FileRef) async throws -> URL {
        if isDemo { return try demoCopy(ref) }
        guard phase == .connected else {
            throw FileError(message: "The HUD isn't linked to the Gateway, so the file can't be fetched.")
        }
        let answer = try await client.request("artifacts.download", .object([
            "sessionKey": .string(ref.sessionKey), "artifactId": .string(ref.file.artifactId),
        ]), timeout: .seconds(60))
        let folder = try filesFolder().appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        let target = folder.appendingPathComponent(ref.file.name)
        if answer["encoding"].string == "base64", let text = answer["data"].string {
            guard let bytes = Data(base64Encoded: text) else {
                throw FileError(message: "The Gateway's copy of the file couldn't be read.")
            }
            try bytes.write(to: target)
        } else if let link = answer["url"].string {
            guard let origin = client.httpOrigin, let url = SentFiles.downloadURL(link, origin: origin) else {
                throw FileError(message: "The Gateway's download link isn't on the Gateway, so the HUD didn't follow it.")
            }
            let (temp, response) = try await Self.fileSession.download(from: url)
            let status = (response as? HTTPURLResponse)?.statusCode
            guard status == 200 else {
                try? FileManager.default.removeItem(at: temp)
                throw FileError(message: "The download failed (HTTP \(status.map(String.init) ?? "status unknown")).")
            }
            try FileManager.default.moveItem(at: temp, to: target)
        } else {
            throw FileError(message: "The Gateway sent neither the file nor a link to it.")
        }
        Self.markDownloaded(target)
        return target
    }

    /// Cookies and caches stay in memory: a ticketed link is used once.
    static let fileSession = URLSession(configuration: .ephemeral)

    /// `$TMPDIR/JorahHUD-files`, emptied the first time it's used in each run of the HUD.
    private func filesFolder() throws -> URL {
        let folder = FileManager.default.temporaryDirectory.appendingPathComponent("JorahHUD-files", isDirectory: true)
        if !filesFolderCleared {
            try? FileManager.default.removeItem(at: folder)
            filesFolderCleared = true
        }
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        return folder
    }

    /// The demo has no Gateway: a Markdown card opens a made-up note, anything else says so.
    private func demoCopy(_ ref: FileRef) throws -> URL {
        guard ref.file.viewer == .markdown else {
            throw FileError(message: "Demo data: there is no real file behind this card.")
        }
        let target = try filesFolder().appendingPathComponent(ref.file.name)
        let note = "# Demo file\n\nMade-up text to show the **viewer**. Not from Jorah.\n\n- one\n- two\n\n```\ncode block\n```\n"
        try Data(note.utf8).write(to: target)
        return target
    }

    /// Fetches a picture's thumbnail for its card. A failure leaves the card's icon: never a stand-in picture.
    func loadThumbnail(_ ref: FileRef) async {
        guard ref.file.viewer == .image, fileThumbnails[ref.key] == nil,
              (ref.file.sizeBytes ?? 0) <= 12_582_912,
              let copy = try? await localCopy(of: ref),
              let source = CGImageSourceCreateWithURL(copy as CFURL, nil)
        else { return }
        let options: [CFString: Any] = [
            kCGImageSourceCreateThumbnailFromImageAlways: true,
            kCGImageSourceCreateThumbnailWithTransform: true,
            kCGImageSourceThumbnailMaxPixelSize: 240,
        ]
        guard let thumbnail = CGImageSourceCreateThumbnailAtIndex(source, 0, options as CFDictionary) else { return }
        fileThumbnails[ref.key] = NSImage(cgImage: thumbnail, size: NSSize(width: thumbnail.width / 2, height: thumbnail.height / 2))
    }

    /// Copies the file into ~/Downloads under a free name ("report 2.pdf" if needed) and shows it in Finder.
    func saveToDownloads(_ ref: FileRef) async throws -> URL {
        let copy = try await localCopy(of: ref)
        let downloads = try FileManager.default.url(for: .downloadsDirectory, in: .userDomainMask, appropriateFor: nil, create: true)
        let name = SentFiles.uniqueName(ref.file.name) {
            FileManager.default.fileExists(atPath: downloads.appendingPathComponent($0).path)
        }
        let target = downloads.appendingPathComponent(name)
        try FileManager.default.copyItem(at: copy, to: target)
        Self.markDownloaded(target)
        NSWorkspace.shared.activateFileViewerSelecting([target])
        return target
    }

    /// Asks where to save the file. Nil when Adam cancels.
    func saveAs(_ ref: FileRef) async throws -> URL? {
        let copy = try await localCopy(of: ref)
        let panel = NSSavePanel()
        panel.nameFieldStringValue = ref.file.name
        panel.canCreateDirectories = true
        panel.directoryURL = FileManager.default.urls(for: .downloadsDirectory, in: .userDomainMask).first
        guard panel.runModal() == .OK, let target = panel.url else { return nil }
        if FileManager.default.fileExists(atPath: target.path) {
            // The panel already asked whether to replace it. Swap in a copy, so a failure keeps the old file.
            let staged = copy.deletingLastPathComponent().appendingPathComponent(UUID().uuidString)
            try FileManager.default.copyItem(at: copy, to: staged)
            _ = try FileManager.default.replaceItemAt(target, withItemAt: staged)
        } else {
            try FileManager.default.copyItem(at: copy, to: target)
        }
        Self.markDownloaded(target)
        return target
    }

    /// Adds the quarantine mark a browser adds, so Gatekeeper checks the file before anything runs it.
    static func markDownloaded(_ url: URL) {
        var values = URLResourceValues()
        values.quarantineProperties = [
            kLSQuarantineAgentNameKey as String: "Jorah HUD",
            kLSQuarantineTypeKey as String: kLSQuarantineTypeOtherDownload as String,
        ]
        var target = url
        try? target.setResourceValues(values)
    }
}
