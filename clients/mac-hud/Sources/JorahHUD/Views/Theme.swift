import SwiftUI

/// One accent on near-black. Glow is decoration only: every state is also written in words.
/// Body text stays in the system face at normal contrast, and mono is for labels.
enum Theme {
    static let background = Color(red: 0.016, green: 0.027, blue: 0.043)
    static let surface = Color.white.opacity(0.035)
    static let stroke = Color(red: 0.36, green: 0.88, blue: 1.0).opacity(0.28)
    static let accent = Color(red: 0.36, green: 0.88, blue: 1.0)
    static let amber = Color(red: 1.0, green: 0.74, blue: 0.30)
    static let red = Color(red: 1.0, green: 0.45, blue: 0.45)
    static let green = Color(red: 0.47, green: 0.95, blue: 0.68)
    static let text = Color(white: 0.93)
    static let dim = Color(white: 0.66)

    static func label(_ size: CGFloat = 10) -> Font {
        .system(size: size, weight: .semibold, design: .monospaced)
    }

    static func mono(_ size: CGFloat = 12) -> Font {
        .system(size: size, weight: .regular, design: .monospaced)
    }
}

/// A framed panel with corner brackets, a title and its own "as of" time.
struct HUDPanel<Content: View>: View {
    let title: String
    var asOf: Date?
    var showsAsOf = true
    var isDemo = false
    @ViewBuilder var content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                Text(title.uppercased())
                    .font(Theme.label(10))
                    .tracking(1.6)
                    .foregroundStyle(Theme.accent)
                Rectangle().fill(Theme.stroke).frame(height: 1)
                if showsAsOf {
                    Text(asOfText)
                        .font(Theme.label(9))
                        .foregroundStyle(isDemo ? Theme.amber : Theme.dim)
                }
            }
            content
        }
        .padding(12)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .background(Theme.surface)
        .overlay(CornerBrackets().stroke(Theme.accent.opacity(0.8), lineWidth: 1))
        .overlay(Rectangle().stroke(Theme.stroke.opacity(0.35), lineWidth: 0.5))
    }

    private var asOfText: String {
        if isDemo { return "DEMO DATA" }
        guard let asOf else { return "AS OF UNKNOWN" }
        return "AS OF " + asOf.formatted(date: .omitted, time: .standard)
    }
}

struct CornerBrackets: Shape {
    var length: CGFloat = 10

    func path(in rect: CGRect) -> Path {
        var path = Path()
        let corners: [(CGPoint, CGFloat, CGFloat)] = [
            (CGPoint(x: rect.minX, y: rect.minY), 1, 1),
            (CGPoint(x: rect.maxX, y: rect.minY), -1, 1),
            (CGPoint(x: rect.minX, y: rect.maxY), 1, -1),
            (CGPoint(x: rect.maxX, y: rect.maxY), -1, -1),
        ]
        for (point, dx, dy) in corners {
            path.move(to: CGPoint(x: point.x + dx * length, y: point.y))
            path.addLine(to: point)
            path.addLine(to: CGPoint(x: point.x, y: point.y + dy * length))
        }
        return path
    }
}

/// Shown wherever a value has not arrived. Never a zero.
struct UnknownText: View {
    var text = "unknown"
    var body: some View {
        Text(text).font(Theme.mono(11)).foregroundStyle(Theme.dim)
    }
}

extension Date {
    var hudTime: String { formatted(date: .omitted, time: .shortened) }

    var hudRelative: String {
        if abs(timeIntervalSinceNow) < 5 { return "just now" }
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .abbreviated
        return formatter.localizedString(for: self, relativeTo: Date())
    }
}
