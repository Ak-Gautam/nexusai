import SwiftUI

struct CommandBarView: View {
    @ObservedObject var state: AppState
    @FocusState private var isInputFocused: Bool

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 12) {
                Image(systemName: "sparkle.magnifyingglass")
                    .foregroundStyle(.secondary)
                    .font(.system(size: 18, weight: .semibold))

                TextField("Ask Nexus or type /downloads", text: $state.commandText)
                    .textFieldStyle(.plain)
                    .font(.system(size: 22, weight: .regular, design: .rounded))
                    .focused($isInputFocused)
                    .onSubmit {
                        Task { await state.submitCommand() }
                    }

                if state.isBusy {
                    ProgressView()
                        .controlSize(.small)
                } else if !state.commandText.isEmpty {
                    Button("Run") {
                        Task { await state.submitCommand() }
                    }
                    .buttonStyle(.borderless)
                    .foregroundStyle(.secondary)
                }
            }
            .padding(.horizontal, 18)
            .padding(.vertical, 16)
            .frame(minWidth: 720)
            .background(.ultraThinMaterial)

            if state.isExpanded {
                Divider()
                VStack(alignment: .leading, spacing: 12) {
                    Text(state.statusText)
                        .font(.system(size: 13, weight: .medium))
                        .foregroundStyle(.secondary)

                    ScrollView {
                        Text(state.responseBody.isEmpty ? "No output yet." : state.responseBody)
                            .font(.system(size: 12, design: .monospaced))
                            .textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .frame(maxHeight: 360)

                    HStack(spacing: 10) {
                        ForEach(state.supportedCommands, id: \.self) { command in
                            Button(command) {
                                state.commandText = command
                                Task { await state.submitCommand() }
                            }
                            .buttonStyle(.bordered)
                        }
                    }
                }
                .padding(18)
                .background(Color(nsColor: .windowBackgroundColor))
            }
        }
        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
        .shadow(color: .black.opacity(0.18), radius: 24, y: 8)
        .onAppear {
            isInputFocused = true
        }
    }
}
