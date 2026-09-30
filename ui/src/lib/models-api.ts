import { detailOf } from "@/lib/vault-note-api"

/**
 * Client for `/api/models` and `PUT /api/personas/{handle}/model` (docs/decisions/044): the one list of models
 * both channels offer, and saving a persona's own model into its `persona.yaml`, the file the terminal's
 * `/model` writes too. The backend decides which models are cloud and which id is acceptable.
 */
export interface ModelOption {
  id: string
  label: string
  short: string
  cloud: boolean
}

export interface ModelsState {
  models: ModelOption[]
  /** The model the persona uses now, whatever decided it. */
  current: string
  currentCloud: boolean
  /** The persona's own saved model, or `null` when it has none. */
  own: string | null
  /** What applies when the persona has none of its own, and whether it is a cloud model. */
  fallback: string
  fallbackCloud: boolean
}

export type ModelsResult =
  | { ok: true; state: ModelsState }
  | { ok: false; error: string }

interface RawModels extends Omit<ModelsState, "currentCloud" | "fallbackCloud"> {
  current_cloud: boolean
  fallback_cloud: boolean
}

const toState = ({ current_cloud, fallback_cloud, ...rest }: RawModels): ModelsState => ({
  ...rest,
  currentCloud: current_cloud,
  fallbackCloud: fallback_cloud,
})

const BACKEND_DOWN = "the Sympose backend is not reachable"

/** `GET /api/models`. */
export async function fetchModels(persona: string): Promise<ModelsResult> {
  try {
    const res = await fetch(`/api/models?persona=${encodeURIComponent(persona)}`)
    if (!res.ok) return { ok: false, error: (await detailOf(res)) || `HTTP ${res.status}` }
    return { ok: true, state: toState((await res.json()) as RawModels) }
  } catch {
    return { ok: false, error: BACKEND_DOWN }
  }
}

/** `PUT /api/personas/{handle}/model`: save `model` as the persona's own, or clear it with `null`. */
export async function chooseModel(persona: string, model: string | null): Promise<ModelsResult> {
  try {
    const res = await fetch(`/api/personas/${encodeURIComponent(persona)}/model`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model }),
    })
    if (!res.ok) return { ok: false, error: (await detailOf(res)) || `Couldn't save the model (HTTP ${res.status})` }
    return { ok: true, state: toState((await res.json()) as RawModels) }
  } catch {
    return { ok: false, error: `Couldn't save the model: ${BACKEND_DOWN}` }
  }
}
