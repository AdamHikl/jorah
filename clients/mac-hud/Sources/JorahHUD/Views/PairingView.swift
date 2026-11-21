import AppKit
import SwiftUI

/// Pairing is Adam's: he types the Gateway token here himself and approves the request on the PC.
/// The token is used for this one connection and is never written to disk.
struct PairingView: View {
    @Environment(HUDModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    @State private var token = ""
    @State private var allowTyping = true

    var body: some View {
        @Bindable var model = model
        VStack(alignment: .leading, spacing: 14) {
            Text("LINK TO JORAH")
                .font(.system(size: 14, weight: .bold, design: .monospaced))
                .tracking(4)
                .foregroundStyle(Theme.accent)

            if case .pairingRequired(let requestId) = model.phase {
                waiting(requestId: requestId)
            } else {
                form
            }

            HStack {
                if case .failed(let reason) = model.phase {
                    Text(reason).font(Theme.mono(11)).foregroundStyle(Theme.red)
                }
                Spacer()
                Button("Close") { dismiss() }
            }
        }
        .padding(22)
        .frame(width: 520)
        .background(Theme.background)
        .preferredColorScheme(.dark)
    }

    private var form: some View {
        @Bindable var model = model
        return VStack(alignment: .leading, spacing: 12) {
            field("GATEWAY ADDRESS") {
                TextField("wss://…", text: $model.gatewayURLText)
                    .textFieldStyle(.roundedBorder)
                    .font(Theme.mono(12))
            }
            field("GATEWAY TOKEN") {
                SecureField("Type or paste it here yourself", text: $token)
                    .textFieldStyle(.roundedBorder)
            }
            Text("Used once to ask for a pairing. It is not saved. After you approve the request on the PC, the HUD keeps its own device token in the Keychain.")
                .font(.system(size: 11))
                .foregroundStyle(Theme.dim)
                .fixedSize(horizontal: false, vertical: true)

            Toggle(isOn: $allowTyping) {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Let me type to Jorah from the HUD").font(.system(size: 12))
                    Text(allowTyping
                        ? "Asks for: operator.read, operator.write"
                        : "Asks for: operator.read (watch only)")
                        .font(Theme.mono(10)).foregroundStyle(Theme.dim)
                }
            }
            Text("The HUD never asks for approvals, pairing or admin access.")
                .font(.system(size: 11)).foregroundStyle(Theme.dim)

            Button(model.phase == .connecting ? "Connecting…" : "Ask to pair") {
                model.pair(sharedToken: token, allowTyping: allowTyping)
                token = ""
            }
            .keyboardShortcut(.defaultAction)
            .disabled(token.isEmpty || model.phase == .connecting)
        }
    }

    private func waiting(requestId: String?) -> some View {
        let command = "openclaw --profile jorah devices approve \(requestId ?? "<request id>")"
        return VStack(alignment: .leading, spacing: 12) {
            Text("The Gateway is waiting for your approval.")
                .font(.system(size: 13)).foregroundStyle(Theme.text)
            field("REQUEST ID") {
                Text(requestId ?? "unknown: run `openclaw --profile jorah devices list` on the PC")
                    .font(Theme.mono(12)).foregroundStyle(Theme.text).textSelection(.enabled)
            }
            field("ON THE PC, AS JORAH'S USER") {
                HStack {
                    Text(command).font(Theme.mono(11)).foregroundStyle(Theme.text).textSelection(.enabled)
                    Spacer()
                    Button("Copy") {
                        NSPasteboard.general.clearContents()
                        NSPasteboard.general.setString(command, forType: .string)
                    }
                }
            }
            Text("Check that the request shows the device name \"Jorah HUD\" and only the access you chose, then approve it.")
                .font(.system(size: 11)).foregroundStyle(Theme.dim)
                .fixedSize(horizontal: false, vertical: true)
            HStack {
                Button("I approved it") { model.client.retry() }
                    .keyboardShortcut(.defaultAction)
                Button("Start over") { model.forgetPairing() }
            }
        }
    }

    private func field<Content: View>(_ label: String, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label).font(Theme.label(9)).tracking(1.2).foregroundStyle(Theme.dim)
            content()
        }
    }
}
