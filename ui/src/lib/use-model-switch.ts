import * as React from "react"

import { confirm } from "@/lib/confirm-store"
import type { SystemKind } from "@/lib/chat-types"
import type { ModelsState } from "@/lib/models-api"

/**
 * Switching the persona's model from the chat (docs/decisions/044). The choice is saved by `choose` (on the
 * persona, as the terminal's `/model` does) and the conversation gets a line saying so. Going from a local
 * model to a cloud one in a conversation that already has replies asks first, through the app's own
 * confirmation: those earlier replies may quote notes and are sent to the cloud model as history whatever the
 * user allows (docs/decisions/031, "A consequence to know": left as it is, but the user is told and accepts).
 * An empty conversation, a switch between cloud models and a switch to a local one ask nothing.
 */
export function useModelSwitch({
  state,
  choose,
  hasReplies,
  notice,
}: {
  state: ModelsState | null
  choose: (model: string | null) => Promise<boolean>
  /** The conversation already holds a reply from the persona. */
  hasReplies: boolean
  notice: (kind: SystemKind, body: string) => void
}) {
  return React.useCallback(
    (model: string | null) => {
      if (!state) return
      const id = model ?? state.fallback
      const listed = state.models.find((m) => m.id === id)
      const cloud = listed ? listed.cloud : model === null ? state.fallbackCloud : true
      const label = listed?.label ?? id
      const apply = async () => {
        if (!(await choose(model))) return
        notice("confirmation", `Switched model to ${label}.${cloud ? "" : " Nothing from your vault leaves your computer."}`)
      }
      if (!state.currentCloud && cloud && hasReplies) {
        confirm({
          message: `Switch to ${label}?`,
          description:
            "Earlier replies in this chat, which may quote your notes, will be sent to the cloud model even if you've limited what it can see. Start a new chat to leave them out.",
          confirmLabel: "Switch model",
          cancelLabel: "Keep the current model",
          tone: "default",
          onConfirm: apply,
        })
        return
      }
      void apply()
    },
    [state, choose, hasReplies, notice]
  )
}
