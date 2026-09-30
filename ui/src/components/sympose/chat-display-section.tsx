import { ControlRow, ControlSection } from "@/components/sympose/control-section"
import { SegmentedControl } from "@/components/sympose/segmented-control"
import type { ChatDisplayPreferences } from "@/lib/use-chat-display-preferences"

/**
 * Settings → Chat: how the web chat draws things (docs/decisions/044). Cookie-backed through
 * `useChatDisplayPreferences`, like the editor and notification sections, and separate from the engine
 * settings: these change only what this page shows, never what the persona is sent or does.
 */
function ChatDisplaySection({
  prefs,
  setPref,
}: {
  prefs: ChatDisplayPreferences
  setPref: <K extends keyof ChatDisplayPreferences>(key: K, value: ChatDisplayPreferences[K]) => void
}) {
  return (
    <ControlSection title="Chat">
      <ControlRow label="Notes a reply was based on">
        <SegmentedControl
          size="sm"
          aria-label="Notes a reply was based on"
          value={prefs.showGrounding ? "on" : "off"}
          onValueChange={(v) => setPref("showGrounding", v === "on")}
          options={[
            { value: "on", label: "On" },
            { value: "off", label: "Off" },
          ]}
        />
      </ControlRow>
      <p className="text-xs text-fg-muted">
        The line under a reply that says which notes it drew on. Hiding it only hides the line; the persona still
        uses them.
      </p>
      <ControlRow label="Type the busy line out by letters">
        <SegmentedControl
          size="sm"
          aria-label="Type the busy line out by letters"
          value={prefs.typeStatus ? "on" : "off"}
          onValueChange={(v) => setPref("typeStatus", v === "on")}
          options={[
            { value: "on", label: "On" },
            { value: "off", label: "Off" },
          ]}
        />
      </ControlRow>
      <p className="text-xs text-fg-muted">
        The line above the message box while a reply is being written. Off shows each phrase at once; a browser set to
        reduce motion does that anyway.
      </p>
    </ControlSection>
  )
}

export { ChatDisplaySection }
