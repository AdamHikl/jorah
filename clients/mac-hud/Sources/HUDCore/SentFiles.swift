import Foundation

/// A file Jorah sent in a reply: a document or a picture from his workspace that the Gateway keeps
/// as a managed artifact. The HUD shows a card for it and downloads the bytes when Adam opens it
/// (a picture also when its card shows, for the thumbnail).
public struct SentFile: Hashable, Codable, Sendable, Identifiable {
    public enum Kind: String, Hashable, Codable, Sendable { case image, audio, video, document }

    public let artifactId: String
    public let kind: Kind
    /// What the reply calls it, made safe to use as a file name.
    public let name: String
    public let mimeType: String?
    public let sizeBytes: Int?
    public var id: String { artifactId }

    public init(artifactId: String, kind: Kind, name: String, mimeType: String?, sizeBytes: Int?) {
        self.artifactId = artifactId
        self.kind = kind
        self.name = name
        self.mimeType = mimeType
        self.sizeBytes = sizeBytes
    }

    /// How the HUD shows it.
    public var viewer: SentFiles.Viewer { SentFiles.viewer(mimeType: mimeType, name: name, kind: kind) }
}

/// Reads the files in an assistant message, as `chat.history` and the `chat` final event carry them.
///
/// OpenClaw 2026.11.6 (source read on the PC, 2026-11-27) turns a standalone `MEDIA:<path>` line in a
/// reply into a display block in the message's `content` array:
/// - a document: `{type: "attachment", attachment: {artifactId, url, kind, label, mimeType, sizeBytes}}`
/// - a picture, sound or video: `{type: "image"|"audio"|"video", artifactId, url, alt | fileName, mimeType, sizeBytes}`
/// A block without an `artifactId` (for example a picture Adam pasted) can't be downloaded and is skipped.
public enum SentFiles {
    public enum Viewer: String, Sendable { case image, pdf, markdown, text, quickLook }

    /// `content` is the message's content array as Foundation JSON (`[Any]`); anything else gives none.
    public static func parse(content: Any?) -> [SentFile] {
        guard let blocks = content as? [Any] else { return [] }
        var files: [SentFile] = []
        for case let block as [String: Any] in blocks {
            guard let file = file(from: block), !files.contains(where: { $0.artifactId == file.artifactId }) else { continue }
            files.append(file)
        }
        return files
    }

    static func file(from block: [String: Any]) -> SentFile? {
        switch block["type"] as? String {
        case "attachment":
            guard let attachment = block["attachment"] as? [String: Any],
                  let id = nonEmpty(attachment["artifactId"]) else { return nil }
            let mime = nonEmpty(attachment["mimeType"])
            let kind: SentFile.Kind = switch attachment["kind"] as? String {
            case "image": .image
            case "audio": .audio
            case "video": .video
            default: .document
            }
            return SentFile(artifactId: id, kind: kind,
                            name: safeFileName(nonEmpty(attachment["label"]) ?? nonEmpty(attachment["fileName"]), mimeType: mime, kind: kind),
                            mimeType: mime, sizeBytes: integer(attachment["sizeBytes"]))
        case "image", "audio", "video":
            guard let id = nonEmpty(block["artifactId"]) else { return nil }
            let kind = SentFile.Kind(rawValue: block["type"] as? String ?? "") ?? .document
            let mime = nonEmpty(block["mimeType"])
            return SentFile(artifactId: id, kind: kind,
                            name: safeFileName(nonEmpty(block["fileName"]) ?? nonEmpty(block["alt"]), mimeType: mime, kind: kind),
                            mimeType: mime, sizeBytes: integer(block["sizeBytes"]))
        default:
            return nil
        }
    }

    /// Picks how to show a file. Office files, archives, audio and video go to Quick Look.
    public static func viewer(mimeType: String?, name: String, kind: SentFile.Kind) -> Viewer {
        let mime = (mimeType ?? "").lowercased()
        let ext = (name as NSString).pathExtension.lowercased()
        if kind == .image || mime.hasPrefix("image/") { return .image }
        if mime == "application/pdf" || ext == "pdf" { return .pdf }
        if mime == "text/markdown" || ["md", "markdown"].contains(ext) { return .markdown }
        let textTypes = ["text/plain", "text/csv", "text/html", "application/json", "application/yaml",
                         "application/x-yaml", "text/yaml"]
        if textTypes.contains(mime) || ["txt", "csv", "json", "yaml", "yml", "log", "html", "htm"].contains(ext) {
            return .text
        }
        return .quickLook
    }

    /// A name that is safe to save on this Mac: no folders, no hidden-file dot, no control characters,
    /// at most 120 characters, and an extension that matches the type when the name has none.
    public static func safeFileName(_ raw: String?, mimeType: String?, kind: SentFile.Kind) -> String {
        var name = (raw ?? "").components(separatedBy: CharacterSet(charactersIn: "/\\:")).last ?? ""
        name = String(name.unicodeScalars.filter { !CharacterSet.controlCharacters.contains($0) }.map(Character.init))
        name = name.trimmingCharacters(in: .whitespacesAndNewlines)
        while name.hasPrefix(".") { name.removeFirst() }
        if name.isEmpty {
            name = switch kind {
            case .image: "picture"
            case .audio: "sound"
            case .video: "video"
            case .document: "file"
            }
        }
        if (name as NSString).pathExtension.isEmpty, let ext = fileExtension(for: mimeType) {
            name += "." + ext
        }
        if name.count > 120 {
            let ext = (name as NSString).pathExtension
            let stem = (name as NSString).deletingPathExtension
            let keep = 120 - (ext.isEmpty ? 0 : ext.count + 1)
            name = String(stem.prefix(max(1, keep))) + (ext.isEmpty ? "" : "." + ext)
        }
        return name
    }

    /// The extension for the types the Gateway lets Jorah send, or nil when unknown.
    public static func fileExtension(for mimeType: String?) -> String? {
        let table: [String: String] = [
            "application/pdf": "pdf", "text/markdown": "md", "text/plain": "txt", "text/csv": "csv",
            "text/html": "html", "application/json": "json", "application/yaml": "yaml", "application/zip": "zip",
            "application/msword": "doc", "application/vnd.ms-excel": "xls", "application/vnd.ms-powerpoint": "ppt",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
            "image/png": "png", "image/jpeg": "jpg", "image/gif": "gif", "image/webp": "webp", "image/heic": "heic",
            "audio/mpeg": "mp3", "audio/mp4": "m4a", "audio/wav": "wav", "video/mp4": "mp4", "video/quicktime": "mov",
        ]
        guard let mime = mimeType?.lowercased().split(separator: ";").first else { return nil }
        return table[mime.trimmingCharacters(in: .whitespaces)]
    }

    /// The first free name in a folder: "report.pdf", then "report 2.pdf", "report 3.pdf", …
    public static func uniqueName(_ name: String, taken: (String) -> Bool) -> String {
        guard taken(name) else { return name }
        let ext = (name as NSString).pathExtension
        let stem = (name as NSString).deletingPathExtension
        for number in 2...999 {
            let candidate = "\(stem) \(number)" + (ext.isEmpty ? "" : ".\(ext)")
            if !taken(candidate) { return candidate }
        }
        return "\(stem) \(UUID().uuidString.prefix(8))" + (ext.isEmpty ? "" : ".\(ext)")
    }

    /// "1.2 MB", or nil when the size is unknown (never a made-up 0).
    public static func sizeLabel(_ bytes: Int?) -> String? {
        guard let bytes, bytes >= 0 else { return nil }
        return ByteCountFormatter.string(fromByteCount: Int64(bytes), countStyle: .file)
    }

    /// The download URL to fetch, built from the Gateway's answer. A path is joined to the Gateway's
    /// own origin; an absolute URL is accepted only on that same origin, so a reply can't make the
    /// HUD fetch from anywhere else.
    public static func downloadURL(_ answer: String, origin: URL) -> URL? {
        guard let scheme = origin.scheme, ["https", "http"].contains(scheme), let host = origin.host else { return nil }
        if answer.hasPrefix("/"), !answer.hasPrefix("//") {
            var base = "\(scheme)://\(host)"
            if let port = origin.port { base += ":\(port)" }
            return URL(string: base + answer)
        }
        guard let url = URL(string: answer), url.scheme == scheme, url.host == host, url.port == origin.port else { return nil }
        return url
    }

    private static func nonEmpty(_ value: Any?) -> String? {
        guard let string = (value as? String)?.trimmingCharacters(in: .whitespacesAndNewlines), !string.isEmpty else { return nil }
        return string
    }

    private static func integer(_ value: Any?) -> Int? {
        switch value {
        case let int as Int: return int
        case let int as Int64: return Int(int)
        case let double as Double where double.isFinite: return Int(double)
        case let number as NSNumber: return number.intValue
        default: return nil
        }
    }
}
