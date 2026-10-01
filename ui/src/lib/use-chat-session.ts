import { useChat } from "@/lib/use-chat"
import { useCloudNotice } from "@/lib/use-cloud-notice"
import { useContextMeter } from "@/lib/use-context-meter"
import { useModels } from "@/lib/use-models"
import { useModelSwitch } from "@/lib/use-model-switch"
import { useSharing } from "@/lib/use-sharing"
import { useStatusPhrases } from "@/lib/use-status-phrases"

/**
 * Everything the chat panel and the Settings sections about it need, for the
 * active persona (docs/decisions/044): the conversation (`chat`), the model in use
 * and the picker's pick (`models`, `switchModel`), the context meter, the busy
 * line's phrases, and what a cloud model may receive (`sharingState`, `setShared`,
 * `cloudNotice`). Each is its own hook; this only wires them together so they agree
 * on the persona, the session and whether the conversation has replies yet (a model
 * switch from a local to a cloud model asks first only once it has).
 *
 * `modelInUse` is the model that answers now; it lets the Persona card follow a
 * pick made in the chat.
 */
export function useChatSession(activePersona: string) {
  const chat = useChat(activePersona)
  const models = useModels(activePersona)
  const modelInUse = models.state?.current
  const hasReplies = chat.turns.some((t) => t.role === "persona")
  const statusPhrases = useStatusPhrases(activePersona, chat.sending)
  const contextFigure = useContextMeter({
    persona: activePersona,
    sessionId: chat.sessionId,
    model: modelInUse,
    real: chat.context,
    hasReplies,
  })
  const switchModel = useModelSwitch({
    state: models.state,
    choose: models.choose,
    hasReplies,
    notice: chat.notice,
  })
  const { state: sharingState, setShared } = useSharing(activePersona, modelInUse)
  const cloudNotice = useCloudNotice(sharingState?.cloud)
  return {
    chat,
    models,
    modelInUse,
    statusPhrases,
    contextFigure,
    switchModel,
    sharingState,
    setShared,
    cloudNotice,
  }
}
