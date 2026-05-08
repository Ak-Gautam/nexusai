import AppKit

/// A borderless, non-activating panel that can still become the key window
/// for text input — similar to how Spotlight and Raycast work.
final class FloatingPanel: NSPanel {
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { false }
}
