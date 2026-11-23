import HUDCore
import SwiftUI
import UniformTypeIdentifiers

struct HUDView: View {
    @Environment(HUDModel.self) private var model

    var body: some View {
        @Bindable var model = model
        VStack(spacing: 12) {
            TopBar()
            HStack(spacing: 12) {
                ConversationView()
                    .frame(minWidth: 300, idealWidth: 380, maxWidth: 440)
                CoreView()
                    .frame(minWidth: 320, maxWidth: .infinity)
                if model.commandMode {
                    VStack(spacing: 12) {
                        WorkStreamView()
                        SubagentsPanel().frame(height: 210)
                    }
                    .frame(minWidth: 280, idealWidth: 360, maxWidth: 420)
                }
            }
            if model.commandMode {
                HStack(spacing: 12) {
                    SessionsPanel()
                    SchedulePanel()
                    DevicesPanel()
                    HealthPanel()
                    PCPanel()
                }
                .frame(height: 190)
            }
        }
        .padding(16)
        .frame(minWidth: 980, minHeight: 640)
        .background(Theme.background)
        .preferredColorScheme(.dark)
        .sheet(isPresented: $model.showPairing) {
            PairingView().environment(model)
        }
        .sheet(isPresented: $model.showPower) {
            PowerView().environment(model)
        }
        .sheet(isPresented: $model.showBrain) {
            BrainView().environment(model)
        }
        .sheet(isPresented: $model.showPhraseSheet) {
            PhraseView().environment(model)
        }
    }
}

// MARK: - Top bar

struct TopBar: View {
    @Environment(HUDModel.self) private var model

    var body: some View {
        @Bindable var model = model
        HStack(spacing: 14) {
            Text("JORAH")
                .font(.system(size: 18, weight: .bold, design: .monospaced))
                .tracking(6)
                .foregroundStyle(Theme.accent)
            LinkPill()
            if model.isDemo {
                Text("DEMO DATA · NOT CONNECTED")
                    .font(Theme.label(10))
                    .padding(.horizontal, 8).padding(.vertical, 3)
                    .foregroundStyle(Theme.background)
                    .background(Theme.amber)
            }
            Spacer()
            TimelineView(.periodic(from: .now, by: 1)) { timeline in
                HStack(spacing: 14) {
                    stat("GATEWAY", model.serverVersion ?? "unknown")
                    stat("UP", uptime(at: timeline.date))
                    stat("LOCAL", timeline.date.formatted(date: .omitted, time: .standard))
                }
            }
            Button {
                model.showBrain = true
            } label: {
                HStack(spacing: 5) {
                    Text("BILLS").font(Theme.label(9)).foregroundStyle(Theme.dim)
                    Text(brainLabel).font(Theme.label(10))
                }
            }
            .disabled(model.isDemo)
            .help("Switch Jorah between your Max plan and the API key")
            .accessibilityLabel("Jorah bills: \(brainLabel)")
            Button {
                model.showPower = true
            } label: {
                Text(model.pausedAt == nil ? "KILL SWITCH" : "RESUME").font(Theme.label(10))
            }
            .tint(model.pausedAt == nil ? Theme.red : Theme.amber)
            .disabled(model.isDemo)
            .help("Pause Jorah on the PC to free its GPU, memory and CPU, or bring it back")
            Toggle(isOn: $model.commandMode) {
                Text(model.commandMode ? "COMMAND" : "CALM").font(Theme.label(10))
            }
            .toggleStyle(.button)
            .help("Switch between the calm view and the full command view")
            Menu {
                Button("Pair or change access…") { model.showPairing = true }
                Button("Voice confirmation phrase…") { model.showPhraseSheet = true }
                    .disabled(model.isDemo)
                Button("Forget this pairing", role: .destructive) { model.forgetPairing() }
            } label: {
                Image(systemName: "gearshape")
            }
            .menuStyle(.borderlessButton)
            .fixedSize()
            .accessibilityLabel("Connection settings")
        }
    }

    private var brainLabel: String {
        if model.brainBusy { return "…" }
        switch model.brainLane {
        case .api: return "API KEY"
        case .max: return "MAX PLAN"
        case .mixed: return "MIXED"
        case .unknown: return "UNKNOWN"
        }
    }

    private func stat(_ name: String, _ value: String) -> some View {
        HStack(spacing: 5) {
            Text(name).font(Theme.label(9)).foregroundStyle(Theme.dim)
            Text(value).font(Theme.mono(11)).foregroundStyle(Theme.text)
        }
    }

    private func uptime(at now: Date) -> String {
        guard let base = model.gatewayUptimeAtHello, model.phase == .connected || model.isDemo else { return "unknown" }
        let seconds = Int(base.ms / 1000 + now.timeIntervalSince(base.at))
        let days = seconds / 86400, hours = (seconds % 86400) / 3600, minutes = (seconds % 3600) / 60
        if days > 0 { return "\(days)d \(hours)h" }
        return "\(hours)h \(minutes)m"
    }
}

struct LinkPill: View {
    @Environment(HUDModel.self) private var model

    var body: some View {
        let (text, color) = description
        HStack(spacing: 6) {
            Circle().fill(color).frame(width: 7, height: 7)
            Text(text).font(Theme.label(10)).foregroundStyle(color)
        }
        .padding(.horizontal, 8).padding(.vertical, 3)
        .overlay(Rectangle().stroke(color.opacity(0.5), lineWidth: 0.5))
        .accessibilityLabel("Link: \(text)")
    }

    private var description: (String, Color) {
        if model.isDemo { return ("NO LINK", Theme.amber) }
        if model.pausedAt != nil { return ("PAUSED ON THE PC", Theme.amber) }
        switch model.phase {
        case .connected:
            return (model.canWrite ? "LINKED · READ + TYPE" : "LINKED · READ ONLY", Theme.green)
        case .connecting: return ("CONNECTING", Theme.amber)
        case .pairingRequired: return ("WAITING FOR APPROVAL", Theme.amber)
        case .idle: return ("NOT CONNECTED", Theme.dim)
        case .failed: return ("LINK FAILED", Theme.red)
        }
    }
}

// MARK: - Centre

struct CoreView: View {
    @Environment(HUDModel.self) private var model

    var body: some View {
        VStack(spacing: 6) {
            ApprovalsPanel()
            TimelineView(.periodic(from: .now, by: 0.5)) { _ in
                let state = model.orbState
                VStack(spacing: 6) {
                    OrbView(state: state, level: model.voiceState.isSessionOpen ? model.voiceLevel : 0)
                        .onTapGesture { model.voice.interrupt() }
                        .help("While Jorah is speaking, click to cut him off")
                    Text(state.rawValue)
                        .font(.system(size: 15, weight: .semibold, design: .monospaced))
                        .tracking(5)
                        .foregroundStyle(state == .offline ? Theme.dim : Theme.text)
                    Text(subtitle(for: state))
                        .font(Theme.mono(11))
                        .foregroundStyle(Theme.dim)
                        .lineLimit(1)
                }
            }
            if case .failed(let reason) = model.phase {
                Text(reason).font(Theme.mono(11)).foregroundStyle(Theme.red).multilineTextAlignment(.center)
            }
            VoiceBar()
            if let full = model.fullReply {
                FullReplyCard(text: full) { model.fullReply = nil }
            }
            EventTicker().frame(height: 74)
        }
        .padding(.vertical, 8)
    }

    private func subtitle(for state: OrbState) -> String {
        if model.voiceState.isSessionOpen {
            switch model.voiceState {
            case .connecting: return "opening the voice link"
            case .listening: return model.lastHeard.map { "heard: \(HUDModel.clip($0, 60))" } ?? "go ahead"
            case .thinking: return model.lastHeard.map { "heard: \(HUDModel.clip($0, 60))" } ?? "thinking"
            case .speaking: return model.lastSpoken.map { HUDModel.clip($0, 70) } ?? "speaking"
            default: break
            }
        }
        switch state {
        case .listening: return "go ahead"
        case .offline: return model.pausedAt == nil ? "no link to the Gateway" : "paused on the PC from this Mac"
        case .acting:
            let running = model.activity.filter { $0.state == .running }
            if let latest = running.last {
                return running.count > 1 ? "\(latest.name) + \(running.count - 1) more" : latest.name
            }
            return ""
        case .thinking: return "\(model.activeRuns.count) run\(model.activeRuns.count == 1 ? "" : "s") in progress"
        case .speaking: return "writing a reply"
        case .idle:
            if model.voiceState == .waitingForWake {
                return model.wakeHeard.map { "say \"Jorah\" · heard: \(HUDModel.clip($0, 50))" } ?? "say \"Jorah\""
            }
            return model.currentSessionKey ?? "session unknown"
        }
    }
}

/// The whole of a long voice reply. Jorah speaks only an overview; "read the whole message" reads this.
struct FullReplyCard: View {
    let text: String
    let onClose: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("FULL MESSAGE").font(Theme.label(9)).foregroundStyle(Theme.accent)
                Spacer()
                Text("say \"read the whole message\"").font(Theme.mono(9)).foregroundStyle(Theme.dim)
                Button(action: onClose) { Image(systemName: "xmark") }
                    .buttonStyle(.plain).foregroundStyle(Theme.dim)
                    .help("Close the full message")
                    .accessibilityLabel("Close the full message")
            }
            ScrollView {
                Text(Self.rendered(text))
                    .font(Theme.mono(11))
                    .foregroundStyle(Theme.text)
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .frame(maxHeight: 160)
        }
        .padding(10)
        .frame(maxWidth: 460)
        .background(Theme.surface, in: RoundedRectangle(cornerRadius: 8))
        .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.stroke, lineWidth: 1))
    }

    /// Bold, code and links from Markdown; bullets and line breaks kept as written.
    static func rendered(_ text: String) -> AttributedString {
        let options = AttributedString.MarkdownParsingOptions(interpretedSyntax: .inlineOnlyPreservingWhitespace)
        return (try? AttributedString(markdown: text, options: options)) ?? AttributedString(text)
    }
}

/// Voice controls, and a plain statement of where the microphone's audio is going.
struct VoiceBar: View {
    @Environment(HUDModel.self) private var model

    var body: some View {
        VStack(spacing: 6) {
            HStack(spacing: 10) {
                Button(model.voiceState.isSessionOpen ? "End" : "Talk") { model.toggleTalk() }
                    .font(Theme.label(11))
                    .keyboardShortcut("t", modifiers: [.command])
                    .help("Open or close a voice session with Jorah (Command-T)")
                if model.voiceState == .speaking {
                    Button("Cut off") { model.voice.interrupt() }.font(Theme.label(11))
                }
                Toggle(isOn: Binding(get: { model.wakeEnabled }, set: { model.setWake($0) })) {
                    Text("WAKE WORD").font(Theme.label(10))
                }
                .toggleStyle(.switch)
                .controlSize(.mini)
                .help("Listen on this Mac for \"Jorah\" or \"hey Jorah\"")
            }
            .disabled(model.isDemo)
            HStack(spacing: 6) {
                Circle().fill(micColor).frame(width: 7, height: 7)
                Text(micText).font(Theme.label(9)).foregroundStyle(micColor)
            }
            .accessibilityElement(children: .combine)
            .accessibilityLabel("Microphone: \(micText)")
            HStack(spacing: 8) {
                Text(verbatim: "Voice confirmation phrase").font(Theme.label(9)).foregroundStyle(Theme.dim)
                Circle().fill(phraseColor).frame(width: 6, height: 6)
                Text(verbatim: phraseText).font(Theme.label(9)).foregroundStyle(phraseColor)
                Button(model.phraseState.isSet == true ? "Change…" : "Set…") {
                    model.showPhraseSheet = true
                }
                .font(Theme.label(9))
                .disabled(model.isDemo)
                .help("Set, change, or remove your voice confirmation phrase")
            }
            if let error = model.voiceError {
                Text(error).font(Theme.mono(10)).foregroundStyle(Theme.red)
                    .multilineTextAlignment(.center).frame(maxWidth: 420)
            }
        }
    }

    private var micText: String {
        if model.isDemo { return "MIC OFF · DEMO" }
        switch model.voiceState {
        case .off: return "MIC OFF"
        case .waitingForWake: return "MIC ON · WAKE WORD ONLY · AUDIO STAYS ON THIS MAC"
        case .connecting: return "OPENING VOICE LINK TO THE PC"
        case .listening, .thinking, .speaking: return "MIC LIVE · AUDIO GOES TO JORAH-VOICE ON THE PC"
        }
    }

    private var micColor: Color {
        switch model.voiceState {
        case .off: return Theme.dim
        case .waitingForWake: return Theme.accent
        default: return Theme.amber
        }
    }

    private var phraseText: String {
        if model.isDemo { return "unknown" }
        if model.phraseBusy { return "checking…" }
        return model.phraseState.summaryText
    }

    private var phraseColor: Color {
        if model.isDemo || model.phraseBusy { return Theme.dim }
        if model.phraseState.isLocked { return Theme.red }
        switch model.phraseState {
        case .set: return Theme.green
        case .notSet, .unknown: return Theme.dim
        }
    }
}

/// The raw event names as they arrive: proof of life for the link.
struct EventTicker: View {
    @Environment(HUDModel.self) private var model

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            ForEach(model.ticker.suffix(4)) { tick in
                HStack(spacing: 8) {
                    Text(tick.at.formatted(date: .omitted, time: .standard))
                        .foregroundStyle(Theme.dim)
                    Text(tick.name).foregroundStyle(Theme.accent.opacity(0.85))
                    Spacer()
                }
                .font(Theme.mono(10))
            }
            if model.ticker.isEmpty {
                Text("no events yet").font(Theme.mono(10)).foregroundStyle(Theme.dim)
            }
            Spacer(minLength: 0)
        }
        .frame(maxWidth: 360, alignment: .leading)
    }
}

// MARK: - Conversation

struct ConversationView: View {
    @Environment(HUDModel.self) private var model
    @FocusState private var focused: Bool

    var body: some View {
        @Bindable var model = model
        HUDPanel(title: "Conversation", asOf: model.historyAsOf, isDemo: model.isDemo) {
            SessionBar()
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 10) {
                        if model.lines.isEmpty {
                            UnknownText(text: model.phase == .connected ? "No messages in this session." : "Transcript unknown until linked.")
                        }
                        ForEach(model.lines) { line in
                            ChatLineView(line: line).id(line.id)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
                .onChange(of: model.lines.last) {
                    if let last = model.lines.last { proxy.scrollTo(last.id, anchor: .bottom) }
                }
            }
            if let error = model.sendError {
                Text(error).font(Theme.mono(11)).foregroundStyle(Theme.red)
            }
            if !model.pendingImages.isEmpty || model.preparingImages > 0 || model.attachNote != nil {
                PendingImagesRow()
            }
            HStack(spacing: 8) {
                Button {
                    pickImages()
                } label: {
                    Image(systemName: "paperclip").font(.system(size: 13))
                }
                .buttonStyle(.plain)
                .foregroundStyle(canSend ? Theme.text : Theme.dim)
                .disabled(!canSend)
                .help("Attach pictures (or paste with ⌘V, or drop them here)")
                .accessibilityLabel("Attach pictures")
                TextField(placeholder, text: $model.draft, axis: .vertical)
                    .textFieldStyle(.plain)
                    .lineLimit(1...4)
                    .font(.system(size: 13))
                    .focused($focused)
                    .disabled(!canSend)
                    .onSubmit { model.send() }
                    .padding(8)
                    .overlay(Rectangle().stroke(dropTargeted ? Theme.accent : Theme.stroke, lineWidth: dropTargeted ? 1 : 0.5))
                if !model.activeRuns.isEmpty, model.canWrite {
                    Button("Stop") { model.stopRun() }
                        .font(Theme.label(10))
                        .help("Stop the run in this session")
                }
                Button("Send") { model.send() }
                    .font(Theme.label(10))
                    .keyboardShortcut(.return, modifiers: .command)
                    .disabled(!canSend || model.preparingImages > 0
                              || (model.draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && model.pendingImages.isEmpty))
            }
            .onDrop(of: [.fileURL, .image], isTargeted: $dropTargeted) { providers in
                guard canSend else { return false }
                return dropImages(providers)
            }
        }
        .onChange(of: focused) { model.composerFocused = focused }
        .onAppear { PasteMonitor.install(model) }
    }

    @State private var dropTargeted = false

    private func pickImages() {
        let panel = NSOpenPanel()
        panel.allowedContentTypes = [.image]
        panel.allowsMultipleSelection = true
        panel.canChooseDirectories = false
        panel.message = "Pictures for Jorah (up to \(ImagePrep.maxImagesPerMessage) per message)"
        guard panel.runModal() == .OK else { return }
        model.attach(urls: panel.urls, origin: "file")
        focused = true
    }

    private func dropImages(_ providers: [NSItemProvider]) -> Bool {
        var accepted = false
        for provider in providers {
            if provider.hasItemConformingToTypeIdentifier(UTType.fileURL.identifier) {
                accepted = true
                _ = provider.loadObject(ofClass: URL.self) { url, _ in
                    guard let url else { return }
                    Task { @MainActor in model.attach(urls: [url], origin: "file") }
                }
            } else if provider.hasItemConformingToTypeIdentifier(UTType.image.identifier) {
                accepted = true
                provider.loadDataRepresentation(forTypeIdentifier: UTType.image.identifier) { data, _ in
                    guard let data else { return }
                    Task { @MainActor in model.attach(data: data, fileName: provider.suggestedName, origin: "file") }
                }
            }
        }
        return accepted
    }

    private var canSend: Bool { model.phase == .connected && model.canWrite && model.currentSessionKey != nil }

    private var placeholder: String {
        if model.isDemo { return "Demo: typing is off" }
        if model.phase != .connected { return "Not linked" }
        if !model.canWrite { return "Read only. Pair again with typing to send." }
        return "Message Jorah"
    }
}

/// Pictures waiting to be sent, each with its size and a remove button.
struct PendingImagesRow: View {
    @Environment(HUDModel.self) private var model

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(model.pendingImages) { item in
                        HStack(spacing: 6) {
                            Image(nsImage: item.thumbnail)
                                .resizable()
                                .aspectRatio(contentMode: .fill)
                                .frame(width: 36, height: 36)
                                .clipped()
                            VStack(alignment: .leading, spacing: 1) {
                                Text(item.prepared.fileName).font(Theme.mono(9)).lineLimit(1).frame(maxWidth: 120, alignment: .leading)
                                Text("\(item.prepared.width)×\(item.prepared.height) · \(Self.size(item.prepared.sizeBytes))")
                                    .font(Theme.mono(9)).foregroundStyle(Theme.dim)
                            }
                            Button {
                                model.removePending(id: item.id)
                            } label: {
                                Image(systemName: "xmark").font(.system(size: 9, weight: .bold))
                            }
                            .buttonStyle(.plain)
                            .foregroundStyle(Theme.dim)
                            .help("Remove this picture")
                            .accessibilityLabel("Remove \(item.prepared.fileName)")
                        }
                        .padding(4)
                        .overlay(Rectangle().stroke(Theme.stroke, lineWidth: 0.5))
                    }
                    if model.preparingImages > 0 {
                        ProgressView().controlSize(.small)
                        Text("Preparing…").font(Theme.mono(9)).foregroundStyle(Theme.dim)
                    }
                }
            }
            if let note = model.attachNote {
                Text(note).font(Theme.mono(10)).foregroundStyle(Theme.amber)
            }
        }
    }

    static func size(_ bytes: Int) -> String {
        bytes >= 1_048_576 ? String(format: "%.1f MB", Double(bytes) / 1_048_576) : "\(max(1, bytes / 1024)) KB"
    }
}

/// ⌘V in the composer with a picture on the clipboard attaches it; anything else pastes as usual.
/// A local key monitor, because the text field's own paste ignores images.
@MainActor
enum PasteMonitor {
    private static var monitor: Any?

    static func install(_ model: HUDModel) {
        guard monitor == nil else { return }
        monitor = NSEvent.addLocalMonitorForEvents(matching: .keyDown) { event in
            let flags = event.modifierFlags.intersection(.deviceIndependentFlagsMask)
            guard flags == .command, event.charactersIgnoringModifiers?.lowercased() == "v",
                  model.composerFocused else { return event }
            return model.attachFromPasteboard() ? nil : event
        }
    }
}

/// Which conversation is on screen, a picker to change it, and a button for a new one.
struct SessionBar: View {
    @Environment(HUDModel.self) private var model

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 8) {
                Menu {
                    if let main = model.mainSessionKey {
                        Button("Main") { model.switchSession(to: main) }
                        Divider()
                    }
                    ForEach(model.sessions.filter { $0.key != model.mainSessionKey && !model.isHomeSession($0) }.prefix(25)) { row in
                        Button(row.active ? "\(row.title)  (running)" : row.title) {
                            model.switchSession(to: row.key)
                        }
                    }
                    if model.sessionsAsOf == nil {
                        Text("Session list unknown")
                    }
                } label: {
                    Text(model.currentSessionTitle).font(Theme.mono(11)).lineLimit(1)
                        .foregroundStyle(Theme.text)
                }
                .menuStyle(.borderlessButton)
                .fixedSize()
                .disabled(model.phase != .connected)
                .help("Choose which conversation to show")
                .accessibilityLabel("Conversation: \(model.currentSessionTitle)")
                Spacer()
                Button {
                    model.newConversation()
                } label: {
                    Label("New", systemImage: "plus").font(Theme.label(10))
                }
                .keyboardShortcut("n", modifiers: [.command])
                .disabled(model.phase != .connected || !model.canWrite)
                .help(model.canWrite ? "Start a new conversation with Jorah (Command-N)" : "Needs typing access. Pair again with typing on.")
            }
            HStack(spacing: 8) {
                Text("MODEL").font(Theme.label(9)).tracking(1.2).foregroundStyle(Theme.dim)
                Menu {
                    Button(model.defaultModel.map { "Default (\($0))" } ?? "Default") { model.setModel(nil) }
                    Divider()
                    ForEach(model.models) { choice in
                        Button {
                            model.setModel(choice.ref)
                        } label: {
                            if choice.ref == model.currentModel {
                                Label(title(choice), systemImage: "checkmark")
                            } else {
                                Text(title(choice))
                            }
                        }
                        .disabled(choice.available == false)
                    }
                    if model.modelsAsOf == nil {
                        Text("Model list unknown")
                    }
                } label: {
                    Text(model.currentModel ?? "unknown")
                        .font(Theme.mono(11)).lineLimit(1)
                        .foregroundStyle(model.currentModel == nil ? Theme.dim : Theme.text)
                }
                .menuStyle(.borderlessButton)
                .fixedSize()
                .disabled(model.phase != .connected || !model.canWrite || model.modelBusy)
                .help(model.canWrite ? "Switch the model for this conversation" : "Needs typing access. Pair again with typing on.")
                .accessibilityLabel("Model: \(model.currentModel ?? "unknown")")
                if model.currentModelSource == "user" {
                    Text("CHOSEN").font(Theme.label(8)).foregroundStyle(Theme.accent)
                } else if model.currentModelSource == "auto" {
                    Text("AUTO").font(Theme.label(8)).foregroundStyle(Theme.dim)
                }
                Spacer()
            }
            if let error = model.modelError {
                Text(error).font(Theme.mono(10)).foregroundStyle(Theme.red)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if !model.isViewingMain {
                Text("Voice talks to this conversation. Telegram talks to Main.")
                    .font(Theme.label(9)).foregroundStyle(Theme.dim)
            }
            if let error = model.sessionError {
                Text(error).font(Theme.mono(10)).foregroundStyle(Theme.red)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }
}

extension SessionBar {
    fileprivate func title(_ choice: ModelChoice) -> String {
        var text = choice.name == choice.id ? choice.ref : "\(choice.name)  (\(choice.ref))"
        if choice.available == false {
            text += "  · unavailable" + (choice.unavailableReason.map { ": \($0)" } ?? "")
        }
        return text
    }
}

struct ChatLineView: View {
    let line: ChatLine

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            HStack(spacing: 6) {
                Text(who).font(Theme.label(9)).tracking(1.2).foregroundStyle(color)
                if let at = line.at {
                    Text(at.hudTime).font(Theme.label(9)).foregroundStyle(Theme.dim)
                }
                if line.streaming {
                    Text("LIVE").font(Theme.label(8)).foregroundStyle(Theme.amber)
                }
            }
            if !line.images.isEmpty {
                HStack(spacing: 6) {
                    ForEach(line.images) { picture in
                        Image(nsImage: picture.image)
                            .resizable()
                            .aspectRatio(contentMode: .fit)
                            .frame(maxWidth: 160, maxHeight: 110, alignment: .leading)
                            .overlay(Rectangle().stroke(Theme.stroke, lineWidth: 0.5))
                            .accessibilityLabel("Picture you sent")
                    }
                }
            }
            if !line.text.isEmpty || line.images.isEmpty {
                Text(line.text.isEmpty ? "…" : line.text)
                    .font(.system(size: 13))
                    .foregroundStyle(line.role == .notice ? Theme.dim : Theme.text)
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .padding(.leading, 8)
        .overlay(alignment: .leading) { Rectangle().fill(color.opacity(0.7)).frame(width: 1.5) }
    }

    private var who: String {
        switch line.role {
        case .user: return "ADAM"
        case .assistant: return "JORAH"
        case .notice: return "NOTE"
        }
    }

    private var color: Color {
        switch line.role {
        case .user: return Theme.dim
        case .assistant: return Theme.accent
        case .notice: return Theme.amber
        }
    }
}

// MARK: - Work stream

struct WorkStreamView: View {
    @Environment(HUDModel.self) private var model

    var body: some View {
        HUDPanel(title: "Work stream", asOf: model.activity.last?.startedAt ?? model.connectedAt, isDemo: model.isDemo) {
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 8) {
                    if model.activity.isEmpty {
                        UnknownText(text: model.phase == .connected
                            ? "No tool calls seen since linking."
                            : "Unknown until linked.")
                    }
                    ForEach(model.activity.reversed()) { item in
                        ActivityRow(item: item)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
    }
}

/// The sub-agents the conversation on screen has spawned. Each is a session of its own.
struct SubagentsPanel: View {
    @Environment(HUDModel.self) private var model

    var body: some View {
        HUDPanel(title: "Sub-agents", asOf: model.subagentsAsOf, isDemo: model.isDemo) {
            if let error = model.subagentsError {
                Text(model.subagentsAsOf == nil ? "unknown: \(error)" : error)
                    .font(Theme.mono(10)).foregroundStyle(Theme.red)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if model.subagentsAsOf == nil {
                if model.subagentsError == nil { UnknownText() }
            } else if model.subagents.isEmpty {
                UnknownText(text: "none spawned by this conversation")
            } else {
                ScrollView {
                    VStack(alignment: .leading, spacing: 7) {
                        ForEach(model.subagents) { row in
                            HStack(alignment: .top, spacing: 7) {
                                Circle().fill(color(row)).frame(width: 6, height: 6).padding(.top, 4)
                                VStack(alignment: .leading, spacing: 1) {
                                    Text(row.title).font(.system(size: 11)).foregroundStyle(Theme.text).lineLimit(2)
                                    Text(detail(row)).font(Theme.label(9)).foregroundStyle(color(row)).lineLimit(1)
                                }
                                Spacer(minLength: 4)
                                if row.isRunning, model.canWrite {
                                    Button("Stop") { model.stopSubagent(row.key) }
                                        .font(Theme.label(9))
                                        .help("Stop this sub-agent and anything it spawned")
                                }
                                Button("Open") { model.switchSession(to: row.key) }
                                    .font(Theme.label(9))
                                    .help("Show this sub-agent's conversation")
                            }
                        }
                    }
                }
            }
        }
    }

    private func detail(_ row: SessionRow) -> String {
        var parts = [row.status ?? (row.active ? "running" : "state unknown")]
        if let model = row.model { parts.append(model) }
        if let started = row.startedAt {
            let end = row.endedAt ?? Date()
            parts.append(row.endedAt == nil ? "since " + started.hudTime : String(format: "%.0fs", end.timeIntervalSince(started)))
        }
        return parts.joined(separator: " · ")
    }

    private func color(_ row: SessionRow) -> Color {
        if row.isRunning { return Theme.amber }
        switch row.status {
        case "done": return Theme.green
        case "failed", "killed", "timeout", "interrupted": return Theme.red
        default: return Theme.dim
        }
    }
}

struct ActivityRow: View {
    let item: ActivityItem

    var body: some View {
        HStack(alignment: .top, spacing: 8) {
            Group {
                switch item.state {
                case .running: ProgressView().controlSize(.mini).tint(Theme.amber)
                case .done: Image(systemName: "checkmark").foregroundStyle(Theme.green)
                case .failed: Image(systemName: "xmark").foregroundStyle(Theme.red)
                }
            }
            .font(.system(size: 10, weight: .bold))
            .frame(width: 14, height: 14)
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 6) {
                    Text(item.name).font(Theme.mono(12)).foregroundStyle(Theme.text)
                    if item.isSubagent {
                        Text("SUB-AGENT").font(Theme.label(8)).foregroundStyle(Theme.accent)
                    }
                    Spacer()
                    Text(timing).font(Theme.label(9)).foregroundStyle(Theme.dim)
                }
                if !item.detail.isEmpty {
                    Text(item.detail).font(Theme.mono(10)).foregroundStyle(Theme.dim).lineLimit(2)
                }
            }
        }
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(item.name), \(stateWord), \(item.detail)")
    }

    private var stateWord: String {
        switch item.state {
        case .running: return "running"
        case .done: return "done"
        case .failed: return "failed"
        }
    }

    private var timing: String {
        guard let ended = item.endedAt else { return "since " + item.startedAt.hudTime }
        let seconds = ended.timeIntervalSince(item.startedAt)
        return seconds < 1 ? item.startedAt.hudTime : String(format: "%.1fs", seconds)
    }
}

// MARK: - Panels

struct SessionsPanel: View {
    @Environment(HUDModel.self) private var model

    private var visibleSessions: [SessionRow] {
        model.sessions.filter { !model.isHomeSession($0) }
    }

    var body: some View {
        HUDPanel(title: "Sessions", asOf: model.sessionsAsOf, isDemo: model.isDemo) {
            if model.sessionsAsOf == nil {
                UnknownText()
            } else if visibleSessions.isEmpty {
                UnknownText(text: "none")
            } else {
                ScrollView {
                    VStack(alignment: .leading, spacing: 5) {
                        ForEach(visibleSessions.prefix(12)) { row in
                            Button {
                                model.switchSession(to: row.key)
                            } label: {
                            HStack(spacing: 6) {
                                Circle().fill(row.active ? Theme.amber : Theme.dim.opacity(0.4)).frame(width: 6, height: 6)
                                Text(row.title).font(.system(size: 11)).foregroundStyle(Theme.text).lineLimit(1)
                                Spacer()
                                Text(row.active ? "running" : (row.updatedAt?.hudRelative ?? "unknown"))
                                    .font(Theme.label(9))
                                    .foregroundStyle(row.active ? Theme.amber : Theme.dim)
                            }
                            .contentShape(Rectangle())
                            }
                            .buttonStyle(.plain)
                            .help("Show this conversation")
                        }
                    }
                }
            }
        }
    }
}

struct SchedulePanel: View {
    @Environment(HUDModel.self) private var model

    var body: some View {
        HUDPanel(title: "Schedule", asOf: model.cronAsOf, isDemo: model.isDemo) {
            if let error = model.cronError, model.cronAsOf == nil {
                UnknownText(text: "unknown: \(error)")
            } else if model.cronAsOf == nil {
                UnknownText()
            } else if model.cron.isEmpty {
                UnknownText(text: "no scheduled jobs")
            } else {
                ScrollView {
                    VStack(alignment: .leading, spacing: 5) {
                        ForEach(model.cron) { job in
                            HStack(spacing: 6) {
                                Text(job.name).font(.system(size: 11))
                                    .foregroundStyle(job.enabled ? Theme.text : Theme.dim).lineLimit(1)
                                Spacer()
                                Text(status(job)).font(Theme.label(9)).foregroundStyle(color(job))
                            }
                        }
                    }
                }
            }
        }
    }

    private func status(_ job: CronRow) -> String {
        if job.running { return "running" }
        if !job.enabled { return "off" }
        if job.lastStatus == "error" { return "last run failed" }
        if let next = job.nextRun { return "next " + next.hudRelative }
        return "next unknown"
    }

    private func color(_ job: CronRow) -> Color {
        if job.running { return Theme.amber }
        if job.enabled, job.lastStatus == "error" { return Theme.red }
        return Theme.dim
    }
}

struct DevicesPanel: View {
    @Environment(HUDModel.self) private var model

    var body: some View {
        HUDPanel(title: "Connected", asOf: model.presenceAsOf, isDemo: model.isDemo) {
            if model.presenceAsOf == nil {
                UnknownText()
            } else if model.presence.isEmpty {
                UnknownText(text: "nothing reported")
            } else {
                ScrollView {
                    VStack(alignment: .leading, spacing: 5) {
                        ForEach(model.presence) { row in
                            VStack(alignment: .leading, spacing: 1) {
                                Text(row.label).font(.system(size: 11)).foregroundStyle(Theme.text).lineLimit(1)
                                Text(row.detail.isEmpty ? "no details" : row.detail)
                                    .font(Theme.label(9)).foregroundStyle(Theme.dim).lineLimit(1)
                            }
                        }
                    }
                }
            }
        }
    }
}

struct HealthPanel: View {
    @Environment(HUDModel.self) private var model

    var body: some View {
        HUDPanel(title: "Health", asOf: model.healthAsOf, isDemo: model.isDemo) {
            VStack(alignment: .leading, spacing: 6) {
                row("Gateway", model.healthOK.map { $0 ? "ok" : "not ok" }, good: model.healthOK)
                row("Channels", model.healthAsOf == nil ? nil : (model.channels.isEmpty ? "none reported" : model.channels.joined(separator: ", ")), good: nil)
                row("Plugin errors", model.pluginErrors.map(String.init), good: model.pluginErrors.map { $0 == 0 })
                row("Heartbeat", model.heartbeatSeconds.map { "every \($0)s" }, good: nil)
                TimelineView(.periodic(from: .now, by: 5)) { _ in
                    row("Last tick", model.lastTickAt?.hudRelative, good: nil)
                }
                row("Access", model.grantedScopes.isEmpty ? nil : model.grantedScopes.map { $0.replacingOccurrences(of: "operator.", with: "") }.joined(separator: ", "), good: nil)
            }
        }
    }

    private func row(_ name: String, _ value: String?, good: Bool?) -> some View {
        HStack(spacing: 6) {
            Text(name).font(Theme.label(9)).foregroundStyle(Theme.dim)
            Spacer()
            Text(value ?? "unknown")
                .font(Theme.mono(11))
                .foregroundStyle(value == nil ? Theme.dim : (good == false ? Theme.red : (good == true ? Theme.green : Theme.text)))
                .lineLimit(1)
        }
    }
}
