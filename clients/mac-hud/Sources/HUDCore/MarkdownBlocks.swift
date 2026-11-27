import Foundation

/// A Markdown document split into the blocks the HUD's viewer draws: headings, paragraphs, lists,
/// quotes, code and tables. Inline marks (bold, italics, code, links) stay in each block's text, for
/// the view to render with `AttributedString(markdown:)`. It is a reader for Jorah's notes, not a full
/// CommonMark parser: anything it doesn't know is shown as a paragraph, so no text is lost.
public enum MarkdownBlock: Equatable, Sendable {
    case heading(level: Int, text: String)
    case paragraph(String)
    /// `marker` is "•", "1.", "☐" or "☑"; `depth` counts indents of two spaces (or one tab).
    case item(marker: String, depth: Int, text: String)
    case quote(String)
    case code(language: String?, text: String)
    case table(String)
    case rule
}

public enum MarkdownBlocks {
    public static func parse(_ source: String) -> [MarkdownBlock] {
        var blocks: [MarkdownBlock] = []
        var paragraph: [String] = []
        var quote: [String] = []
        var table: [String] = []
        var fence: (marker: String, language: String?, lines: [String])?

        func flush() {
            if !paragraph.isEmpty { blocks.append(.paragraph(paragraph.joined(separator: " "))); paragraph = [] }
            if !quote.isEmpty { blocks.append(.quote(quote.joined(separator: "\n"))); quote = [] }
            if !table.isEmpty { blocks.append(.table(table.joined(separator: "\n"))); table = [] }
        }

        let lines = source.replacingOccurrences(of: "\r\n", with: "\n").components(separatedBy: "\n")
        for raw in lines {
            if let open = fence {
                if raw.trimmingCharacters(in: .whitespaces).hasPrefix(open.marker) {
                    blocks.append(.code(language: open.language, text: open.lines.joined(separator: "\n")))
                    fence = nil
                } else {
                    fence?.lines.append(raw)
                }
                continue
            }
            let line = raw.trimmingCharacters(in: .whitespaces)
            if line.isEmpty { flush(); continue }

            if line.hasPrefix("```") || line.hasPrefix("~~~") {
                flush()
                let marker = String(line.prefix(3))
                let language = line.dropFirst(3).trimmingCharacters(in: .whitespaces)
                fence = (marker, language.isEmpty ? nil : language, [])
                continue
            }
            if let heading = heading(line) { flush(); blocks.append(heading); continue }
            if isRule(line) { flush(); blocks.append(.rule); continue }
            if line.hasPrefix(">") {
                if !paragraph.isEmpty || !table.isEmpty { flush() }
                quote.append(String(line.dropFirst()).trimmingCharacters(in: .whitespaces))
                continue
            }
            if line.hasPrefix("|") {
                if !paragraph.isEmpty || !quote.isEmpty { flush() }
                table.append(line)
                continue
            }
            if let item = item(raw) { flush(); blocks.append(item); continue }
            if !quote.isEmpty || !table.isEmpty { flush() }
            paragraph.append(line)
        }
        if let open = fence { blocks.append(.code(language: open.language, text: open.lines.joined(separator: "\n"))) }
        flush()
        return blocks
    }

    static func heading(_ line: String) -> MarkdownBlock? {
        let hashes = line.prefix { $0 == "#" }.count
        guard (1...6).contains(hashes) else { return nil }
        let rest = line.dropFirst(hashes)
        guard rest.isEmpty || rest.first == " " else { return nil }
        var text = rest.trimmingCharacters(in: .whitespaces)
        while text.hasSuffix("#") { text.removeLast() }
        return .heading(level: hashes, text: text.trimmingCharacters(in: .whitespaces))
    }

    static func isRule(_ line: String) -> Bool {
        let compact = line.replacingOccurrences(of: " ", with: "")
        guard compact.count >= 3, let first = compact.first, "-*_".contains(first) else { return false }
        return compact.allSatisfy { $0 == first }
    }

    static func item(_ raw: String) -> MarkdownBlock? {
        var indent = 0
        for character in raw {
            if character == " " { indent += 1 } else if character == "\t" { indent += 2 } else { break }
        }
        let line = raw.trimmingCharacters(in: .whitespaces)
        let depth = min(indent / 2, 6)
        for bullet in ["- ", "* ", "+ "] where line.hasPrefix(bullet) {
            var text = String(line.dropFirst(2))
            var marker = "•"
            if text.hasPrefix("[ ] ") { marker = "☐"; text.removeFirst(4) }
            else if text.lowercased().hasPrefix("[x] ") { marker = "☑"; text.removeFirst(4) }
            return .item(marker: marker, depth: depth, text: text)
        }
        let digits = line.prefix { $0.isNumber }
        guard !digits.isEmpty, digits.count <= 4 else { return nil }
        let after = line.dropFirst(digits.count)
        guard let punctuation = after.first, punctuation == "." || punctuation == ")",
              after.dropFirst().first == " " else { return nil }
        return .item(marker: "\(digits).", depth: depth, text: String(after.dropFirst(2)))
    }
}
