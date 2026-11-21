import SwiftUI

/// The core. It shows Jorah's state by motion and brightness, and the state is always
/// written underneath, so nothing depends on seeing the animation.
struct OrbView: View {
    let state: OrbState
    /// Loudness of the mic or of Jorah's voice, 0 to 1. Zero when no voice session is open.
    var level: Double = 0
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        TimelineView(.animation(minimumInterval: 1.0 / 60.0, paused: reduceMotion)) { timeline in
            Canvas { context, size in
                let t = reduceMotion ? 0 : timeline.date.timeIntervalSinceReferenceDate
                draw(&context, size: size, t: t)
            }
        }
        .accessibilityElement()
        .accessibilityLabel("Jorah is \(state.rawValue.lowercased())")
    }

    private var energy: Double {
        min(1, baseEnergy + level * 0.5)
    }

    private var baseEnergy: Double {
        switch state {
        case .offline: return 0.06
        case .listening: return 0.45
        case .idle: return 0.28
        case .thinking: return 0.6
        case .speaking: return 0.75
        case .acting: return 0.9
        }
    }

    private var tint: Color {
        switch state {
        case .offline: return Theme.dim
        case .acting: return Theme.amber
        default: return Theme.accent
        }
    }

    private func draw(_ context: inout GraphicsContext, size: CGSize, t: Double) {
        let center = CGPoint(x: size.width / 2, y: size.height / 2)
        let radius = min(size.width, size.height) * 0.42
        let e = energy
        let breathe = 0.5 + 0.5 * sin(t * (0.8 + e * 2.2))

        // Soft halo.
        let halo = Path(ellipseIn: CGRect(x: center.x - radius * 1.15, y: center.y - radius * 1.15,
                                          width: radius * 2.3, height: radius * 2.3))
        context.fill(halo, with: .radialGradient(
            Gradient(colors: [tint.opacity(0.10 + 0.16 * e), tint.opacity(0.03), .clear]),
            center: center, startRadius: radius * 0.1, endRadius: radius * 1.15))

        // Outer tick ring.
        var ticks = Path()
        let tickCount = 96
        let spin = t * 0.04 * (0.5 + e)
        for index in 0..<tickCount {
            let angle = Double(index) / Double(tickCount) * 2 * .pi + spin
            let long = index % 8 == 0
            let inner = radius * (long ? 0.93 : 0.96)
            ticks.move(to: point(center, inner, angle))
            ticks.addLine(to: point(center, radius, angle))
        }
        context.stroke(ticks, with: .color(tint.opacity(0.55)), lineWidth: 1)

        // Segmented rings, turning against each other.
        let rings: [(Double, Double, Int, Double, CGFloat)] = [
            (0.84, 0.35, 3, 0.62, 2.0),
            (0.74, -0.55, 5, 0.38, 1.0),
            (0.64, 0.8, 2, 0.8, 1.5),
        ]
        for (scale, speed, count, fill, width) in rings {
            var arcs = Path()
            let rotation = t * speed * (0.3 + e)
            for index in 0..<count {
                let start = Double(index) / Double(count) * 2 * .pi + rotation
                let end = start + (2 * .pi / Double(count)) * fill
                arcs.move(to: point(center, radius * scale, start))
                arcs.addArc(center: center, radius: radius * scale,
                            startAngle: .radians(start), endAngle: .radians(end), clockwise: false)
            }
            context.stroke(arcs, with: .color(tint.opacity(0.35 + 0.45 * e)),
                           style: StrokeStyle(lineWidth: width, lineCap: .butt))
        }

        // The living ring: a circle bent by a few sine waves. More energy, more movement.
        var glowLayer = context
        glowLayer.addFilter(.shadow(color: tint.opacity(0.9), radius: 10 + 14 * e))
        for layer in 0..<3 {
            var wave = Path()
            let steps = 180
            let base = radius * (0.44 + 0.03 * Double(layer))
            for step in 0...steps {
                let angle = Double(step) / Double(steps) * 2 * .pi
                let wobble =
                    sin(angle * 3 + t * (1.1 + e * 2) + Double(layer)) * 0.035
                    + sin(angle * 7 - t * (1.7 + e * 3)) * 0.02
                    + sin(angle * 13 + t * (2.3 + e * 5) + Double(layer) * 2) * 0.012
                let r = base * (1 + wobble * (0.25 + e * 1.6 + level * 2.2) + level * 0.08)
                let p = point(center, r, angle)
                if step == 0 { wave.move(to: p) } else { wave.addLine(to: p) }
            }
            wave.closeSubpath()
            glowLayer.stroke(wave, with: .color(tint.opacity(0.85 - 0.22 * Double(layer))),
                             lineWidth: layer == 0 ? 1.8 : 1.0)
        }

        // Core.
        let coreRadius = radius * (0.2 + 0.05 * breathe * (0.4 + e) + 0.1 * level)
        let core = Path(ellipseIn: CGRect(x: center.x - coreRadius, y: center.y - coreRadius,
                                          width: coreRadius * 2, height: coreRadius * 2))
        context.fill(core, with: .radialGradient(
            Gradient(colors: [Color.white.opacity(0.75 * (0.3 + e)), tint.opacity(0.55 * (0.3 + e)), .clear]),
            center: center, startRadius: 0, endRadius: coreRadius))
    }

    private func point(_ center: CGPoint, _ radius: Double, _ angle: Double) -> CGPoint {
        CGPoint(x: center.x + CGFloat(cos(angle) * radius), y: center.y + CGFloat(sin(angle) * radius))
    }
}
