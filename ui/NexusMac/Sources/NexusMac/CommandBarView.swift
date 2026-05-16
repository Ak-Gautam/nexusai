import SwiftUI

struct CommandBarView: View {
    @ObservedObject var state: AppState
    @FocusState private var isInputFocused: Bool

    var body: some View {
        VStack(spacing: 0) {

            // ── Command input bar ──
            HStack(spacing: 12) {
                Image(systemName: "sparkle.magnifyingglass")
                    .foregroundStyle(.secondary)
                    .font(.system(size: 18, weight: .semibold))

                TextField("Ask Nexus or type a /command…", text: $state.commandText)
                    .textFieldStyle(.plain)
                    .font(.system(size: 20, weight: .regular, design: .rounded))
                    .focused($isInputFocused)
                    .onSubmit {
                        Task { await state.submitCommand() }
                    }

                if state.isBusy {
                    ProgressView()
                        .controlSize(.small)
                } else if !state.commandText.isEmpty {
                    Button {
                        Task { await state.submitCommand() }
                    } label: {
                        Image(systemName: "return")
                            .font(.system(size: 14, weight: .semibold))
                            .foregroundStyle(.secondary)
                    }
                    .buttonStyle(.borderless)
                }
            }
            .padding(.horizontal, 18)
            .padding(.vertical, 14)

            // ── Expanded results area ──
            if state.isExpanded {
                Divider()
                    .padding(.horizontal, 12)

                VStack(alignment: .leading, spacing: 10) {
                    HStack {
                        Text(state.statusText)
                            .font(.system(size: 12, weight: .medium))
                            .foregroundStyle(.tertiary)
                        Spacer()
                        if state.isBusy {
                            ProgressView()
                                .controlSize(.mini)
                        }
                    }

                    Label(state.runtimeSummary, systemImage: state.runtimeStatus?.loaded == true ? "cpu.fill" : "cpu")
                        .font(.system(size: 12, weight: .medium))
                        .foregroundStyle(state.runtimeStatus?.loaded == true ? .primary : .secondary)
                        .lineLimit(1)

                    ScrollView {
                        if state.isShowingChatTranscript && !state.chatTranscript.isEmpty {
                            VStack(alignment: .leading, spacing: 12) {
                                ForEach(state.chatTranscript) { message in
                                    HStack(alignment: .top, spacing: 10) {
                                        Text(message.role == .user ? "You" : "Nexus")
                                            .font(.system(size: 11, weight: .semibold))
                                            .foregroundStyle(.secondary)
                                            .frame(width: 42, alignment: .leading)

                                        Text(message.content)
                                            .font(.system(size: 12.5))
                                            .textSelection(.enabled)
                                            .frame(maxWidth: .infinity, alignment: .leading)
                                    }
                                }
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                        } else {
                            Text(state.responseBody.isEmpty ? "Waiting…" : state.responseBody)
                                .font(.system(size: 11.5, design: .monospaced))
                                .textSelection(.enabled)
                                .frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }
                    .frame(maxHeight: 320)

                    Divider()

                    if !state.loadableModels.isEmpty {
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 8) {
                                ForEach(state.loadableModels) { artifact in
                                    Button {
                                        Task { await state.loadModel(artifact) }
                                    } label: {
                                        Label(artifact.name, systemImage: "bolt.fill")
                                            .lineLimit(1)
                                    }
                                    .buttonStyle(.bordered)
                                    .controlSize(.small)
                                    .disabled(state.isBusy)
                                }
                            }
                        }
                    }

                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 8) {
                            ForEach(state.supportedCommands, id: \.self) { cmd in
                                Button(cmd) {
                                    state.commandText = cmd
                                    Task { await state.submitCommand() }
                                }
                                .buttonStyle(.bordered)
                                .controlSize(.small)
                            }
                        }
                    }
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 12)
            }
        }
        .background(.ultraThinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .strokeBorder(Color.primary.opacity(0.08), lineWidth: 0.5)
        )
        .shadow(color: .black.opacity(0.18), radius: 20, y: 6)
        .onAppear {
            isInputFocused = true
        }
        .task {
            await state.refreshModelCatalogIfNeeded()
            await state.refreshRuntimeStatusIfNeeded()
        }
        .onChange(of: state.focusTrigger) { _, _ in
            isInputFocused = true
        }
    }
}
