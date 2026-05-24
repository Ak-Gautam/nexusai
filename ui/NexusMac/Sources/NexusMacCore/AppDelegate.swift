import AppKit
import SwiftUI

extension Notification.Name {
    static let nexusTogglePanel = Notification.Name("nexusTogglePanel")
    static let nexusHidePanel = Notification.Name("nexusHidePanel")
    static let nexusPanelExpand = Notification.Name("nexusPanelExpand")
}

@MainActor
public final class AppDelegate: NSObject, NSApplicationDelegate {
    private var panel: FloatingPanel?
    private var state: AppState?
    private var statusItem: NSStatusItem?
    private var globalMonitor: Any?
    private var localMonitor: Any?

    public nonisolated override init() {
        super.init()
    }

    public func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)

        let appState = AppState()
        self.state = appState

        // ── Build the floating panel ──
        let panel = FloatingPanel(
            contentRect: NSRect(x: 0, y: 0, width: 720, height: 56),
            styleMask: [.nonactivatingPanel],
            backing: .buffered,
            defer: false
        )
        panel.titlebarAppearsTransparent = true
        panel.titleVisibility = .hidden
        panel.isMovableByWindowBackground = true
        panel.level = .floating
        panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .transient]
        panel.isOpaque = false
        panel.backgroundColor = .clear
        panel.hasShadow = false          // SwiftUI adds its own shadow matching the rounded shape
        panel.isReleasedWhenClosed = false
        panel.animationBehavior = .utilityWindow

        let contentView = CommandBarView(state: appState)
        panel.contentView = NSHostingView(rootView: contentView)
        self.panel = panel

        setupStatusBar()
        setupHotkeys()
        setupObservers()
        FrontendLogger.shared.info("application_launched", metadata: ["frontend_log": FrontendLogger.shared.logFileURL.path])
        showPanel()
    }

    // MARK: - Menu-bar icon

    private func setupStatusBar() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.squareLength)
        if let button = statusItem?.button {
            button.image = NSImage(
                systemSymbolName: "sparkle.magnifyingglass",
                accessibilityDescription: "Nexus"
            )
        }
        let menu = NSMenu()
        let toggle = NSMenuItem(
            title: "Toggle Nexus (⌃Space)",
            action: #selector(togglePanelObjc),
            keyEquivalent: ""
        )
        toggle.target = self
        menu.addItem(toggle)
        menu.addItem(.separator())
        menu.addItem(
            withTitle: "Quit Nexus",
            action: #selector(NSApplication.terminate(_:)),
            keyEquivalent: "q"
        )
        statusItem?.menu = menu
    }

    @objc private func togglePanelObjc() {
        togglePanel()
    }

    // MARK: - Global / local hotkeys

    private func setupHotkeys() {
        // Notifications keep closures free of @MainActor captures.
        globalMonitor = NSEvent.addGlobalMonitorForEvents(matching: .keyDown) { event in
            if event.modifierFlags.intersection(.deviceIndependentFlagsMask) == .control,
               event.keyCode == 49 {
                NotificationCenter.default.post(name: .nexusTogglePanel, object: nil)
            }
        }
        localMonitor = NSEvent.addLocalMonitorForEvents(matching: .keyDown) { event in
            if event.modifierFlags.intersection(.deviceIndependentFlagsMask) == .control,
               event.keyCode == 49 {
                NotificationCenter.default.post(name: .nexusTogglePanel, object: nil)
                return nil
            }
            if event.keyCode == 53 { // Escape
                NotificationCenter.default.post(name: .nexusHidePanel, object: nil)
                return nil
            }
            return event
        }
    }

    // MARK: - Notification observers

    private func setupObservers() {
        NotificationCenter.default.addObserver(
            forName: .nexusTogglePanel, object: nil, queue: .main
        ) { [weak self] _ in
            Task { @MainActor in self?.togglePanel() }
        }
        NotificationCenter.default.addObserver(
            forName: .nexusHidePanel, object: nil, queue: .main
        ) { [weak self] _ in
            Task { @MainActor in self?.hidePanel() }
        }
        NotificationCenter.default.addObserver(
            forName: .nexusPanelExpand, object: nil, queue: .main
        ) { [weak self] _ in
            Task { @MainActor in self?.resizePanel(expanded: true) }
        }
    }

    // MARK: - Panel control

    private func togglePanel() {
        guard let panel else { return }
        if panel.isVisible { hidePanel() } else { showPanel() }
    }

    private func showPanel() {
        guard let panel else { return }
        FrontendLogger.shared.info("panel_shown")
        state?.reset()
        resizePanel(expanded: false)
        centerPanel()
        panel.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    private func hidePanel() {
        FrontendLogger.shared.info("panel_hidden")
        panel?.orderOut(nil)
    }

    private func centerPanel() {
        guard let panel, let screen = NSScreen.main else { return }
        let visible = screen.visibleFrame
        let x = visible.origin.x + (visible.width - panel.frame.width) / 2
        let y = visible.origin.y + visible.height * 0.65
        panel.setFrameOrigin(NSPoint(x: x, y: y))
    }

    private func resizePanel(expanded: Bool) {
        guard let panel else { return }
        let targetHeight: CGFloat = expanded ? 460 : 56
        FrontendLogger.shared.info("panel_resized", metadata: ["expanded": "\(expanded)", "height": "\(Int(targetHeight))"])
        var frame = panel.frame
        let topEdge = frame.origin.y + frame.height
        frame.size.height = targetHeight
        frame.origin.y = topEdge - targetHeight
        NSAnimationContext.runAnimationGroup { context in
            context.duration = 0.25
            context.timingFunction = CAMediaTimingFunction(name: .easeInEaseOut)
            panel.animator().setFrame(frame, display: true)
        }
    }
}
