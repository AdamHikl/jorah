import CoreGraphics
import Foundation
import ImageIO
import UniformTypeIdentifiers

/// An image ready for `chat.send`: bytes the Gateway accepts, at most `ImagePrep.maxSide` pixels on
/// its longest side and `ImagePrep.maxBytes` bytes.
public struct PreparedImage: Equatable, Sendable {
    public let data: Data
    public let mimeType: String
    public let fileName: String
    public let width: Int
    public let height: Int
    public var sizeBytes: Int { data.count }
}

public enum ImagePrepError: Error, Equatable, LocalizedError {
    case notAnImage
    case sourceTooLarge(Int)
    case tooLarge
    case animatedTooLarge

    public var errorDescription: String? {
        switch self {
        case .notAnImage: return "not an image this Mac can read"
        case .sourceTooLarge(let bytes): return "the file is \(bytes / 1_048_576) MB, over the 64 MB the HUD reads"
        case .tooLarge: return "still over 5 MB after shrinking"
        case .animatedTooLarge: return "an animated GIF over 5 MB or 2048 px can't be shrunk without losing frames"
        }
    }
}

/// Turns pasted, dropped or picked image bytes into what the Gateway takes.
///
/// The Gateway (OpenClaw 2026.11.6, `parseMessageWithAttachments`) refuses an image over 6 MB and
/// keeps images up to 2 MB inline for the model, saving larger ones to its media store. JPEG, PNG,
/// WebP and GIF within both limits are sent as they are; anything else (HEIC, TIFF, a large or
/// rotated photo) is redrawn: PNG when it has transparency, else JPEG, shrinking until it fits.
public enum ImagePrep {
    public static let maxSide = 2048
    public static let maxBytes = 5 * 1024 * 1024
    public static let maxSourceBytes = 64 * 1024 * 1024
    public static let maxImagesPerMessage = 4

    static let sentAsIs: [String: (mime: String, ext: String)] = [
        UTType.jpeg.identifier: ("image/jpeg", "jpg"),
        UTType.png.identifier: ("image/png", "png"),
        UTType.webP.identifier: ("image/webp", "webp"),
        UTType.gif.identifier: ("image/gif", "gif"),
    ]

    public static func prepare(_ source: Data, fileName: String?) throws -> PreparedImage {
        guard source.count <= maxSourceBytes else { throw ImagePrepError.sourceTooLarge(source.count) }
        guard let image = CGImageSourceCreateWithData(source as CFData, [kCGImageSourceShouldCache: false] as CFDictionary),
              let type = CGImageSourceGetType(image) as String?,
              CGImageSourceGetCount(image) > 0,
              let props = CGImageSourceCopyPropertiesAtIndex(image, 0, nil) as? [CFString: Any],
              let width = (props[kCGImagePropertyPixelWidth] as? NSNumber)?.intValue,
              let height = (props[kCGImagePropertyPixelHeight] as? NSNumber)?.intValue,
              width > 0, height > 0
        else { throw ImagePrepError.notAnImage }

        let orientation = (props[kCGImagePropertyOrientation] as? NSNumber)?.intValue ?? 1
        let base = baseName(fileName)
        if let kept = sentAsIs[type], max(width, height) <= maxSide, source.count <= maxBytes, orientation == 1 {
            return PreparedImage(data: source, mimeType: kept.mime, fileName: "\(base).\(kept.ext)", width: width, height: height)
        }
        if type == UTType.gif.identifier, CGImageSourceGetCount(image) > 1 { throw ImagePrepError.animatedTooLarge }

        let hasAlpha = (props[kCGImagePropertyHasAlpha] as? Bool) ?? false
        let longest = max(width, height)
        var sides: [Int] = []
        for side in [maxSide, 1600, 1280, 1024] where !sides.contains(min(side, longest)) { sides.append(min(side, longest)) }
        for side in sides {
            let options: [CFString: Any] = [
                kCGImageSourceCreateThumbnailFromImageAlways: true,
                kCGImageSourceCreateThumbnailWithTransform: true,
                kCGImageSourceThumbnailMaxPixelSize: side,
                kCGImageSourceShouldCacheImmediately: true,
            ]
            guard let drawn = CGImageSourceCreateThumbnailAtIndex(image, 0, options as CFDictionary) else {
                throw ImagePrepError.notAnImage
            }
            var tries: [(UTType, Double?)] = []
            if hasAlpha { tries.append((.png, nil)) }
            tries += [(.jpeg, 0.85), (.jpeg, 0.7)]
            for (format, quality) in tries {
                guard let data = encode(drawn, as: format, quality: quality) else { continue }
                if data.count <= maxBytes {
                    let png = format == .png
                    return PreparedImage(data: data, mimeType: png ? "image/png" : "image/jpeg",
                                         fileName: "\(base).\(png ? "png" : "jpg")",
                                         width: drawn.width, height: drawn.height)
                }
            }
        }
        // A last try well under the limit, for pathological noise.
        let options: [CFString: Any] = [
            kCGImageSourceCreateThumbnailFromImageAlways: true,
            kCGImageSourceCreateThumbnailWithTransform: true,
            kCGImageSourceThumbnailMaxPixelSize: min(1024, longest),
        ]
        if let drawn = CGImageSourceCreateThumbnailAtIndex(image, 0, options as CFDictionary),
           let data = encode(drawn, as: .jpeg, quality: 0.5), data.count <= maxBytes {
            return PreparedImage(data: data, mimeType: "image/jpeg", fileName: "\(base).jpg", width: drawn.width, height: drawn.height)
        }
        throw ImagePrepError.tooLarge
    }

    /// PNG keeps transparency; JPEG is drawn on white first, so transparent parts don't turn black.
    static func encode(_ image: CGImage, as format: UTType, quality: Double?) -> Data? {
        var source = image
        if format == .jpeg {
            guard let context = CGContext(data: nil, width: image.width, height: image.height, bitsPerComponent: 8, bytesPerRow: 0,
                                          space: CGColorSpace(name: CGColorSpace.sRGB)!,
                                          bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue) else { return nil }
            let rect = CGRect(x: 0, y: 0, width: image.width, height: image.height)
            context.setFillColor(CGColor(red: 1, green: 1, blue: 1, alpha: 1))
            context.fill(rect)
            context.draw(image, in: rect)
            guard let flat = context.makeImage() else { return nil }
            source = flat
        }
        let out = NSMutableData()
        guard let dest = CGImageDestinationCreateWithData(out, format.identifier as CFString, 1, nil) else { return nil }
        var props: [CFString: Any] = [:]
        if let quality { props[kCGImageDestinationLossyCompressionQuality] = quality }
        CGImageDestinationAddImage(dest, source, props as CFDictionary)
        guard CGImageDestinationFinalize(dest) else { return nil }
        return out as Data
    }

    /// A safe file name without extension: the given name's letters (accents dropped), digits, dots, dashes and
    /// underscores, at most 60 characters, or "pasted-image".
    public static func baseName(_ fileName: String?) -> String {
        guard let fileName, !fileName.isEmpty else { return "pasted-image" }
        let last = (fileName as NSString).lastPathComponent
        let stem = (last as NSString).deletingPathExtension.folding(options: .diacriticInsensitive, locale: nil)
        let allowed = CharacterSet.alphanumerics.union(CharacterSet(charactersIn: "-_."))
        var cleaned = String(stem.unicodeScalars.map { allowed.contains($0) && $0.isASCII ? Character($0) : "-" })
        while cleaned.contains("--") { cleaned = cleaned.replacingOccurrences(of: "--", with: "-") }
        cleaned = cleaned.trimmingCharacters(in: CharacterSet(charactersIn: "-."))
        if cleaned.count > 60 { cleaned = String(cleaned.prefix(60)) }
        return cleaned.isEmpty ? "pasted-image" : cleaned
    }
}

/// Pictures in a transcript message, as `chat.history` returns it.
public enum HistoryPictures {
    /// The Gateway appends `[media attached: media://inbound/<id>]` for each image it saved instead
    /// of passing inline. Returns the text without those lines and how many there were.
    public static func strippingMarkers(_ text: String) -> (text: String, count: Int) {
        var count = 0
        let kept = text.components(separatedBy: "\n").filter { line in
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            if trimmed.hasPrefix("[media attached:"), trimmed.hasSuffix("]") {
                count += 1
                return false
            }
            return true
        }
        return (kept.joined(separator: "\n").trimmingCharacters(in: .whitespacesAndNewlines), count)
    }

    public static func label(_ count: Int) -> String {
        count == 1 ? "🖼 1 picture" : "🖼 \(count) pictures"
    }

    /// The text without a leading `label(_:)` line, as it was typed.
    public static func withoutLabel(_ text: String) -> String {
        guard text.hasPrefix("🖼 ") else { return text }
        let firstLine = text.prefix { $0 != "\n" }
        guard firstLine.hasSuffix(" picture") || firstLine.hasSuffix(" pictures") else { return text }
        return String(text.dropFirst(firstLine.count)).trimmingCharacters(in: .whitespacesAndNewlines)
    }
}
