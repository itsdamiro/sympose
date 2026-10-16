import { ICON_SET } from "@/lib/persona-icons"

/**
 * What a person might type to find an icon, besides its name (docs/decisions/087): `food` finds the chef's hat, `film`
 * the film roll. An icon with no entry (most of the catalogue, docs/decisions/088) is found by its name alone. Matching is
 * done here, in the browser: the set is under a thousand names, so there is nothing to ask a server.
 */
const KEYWORDS: Record<string, string[]> = {
  airplane: ["travel", "trip", "flight", "holiday", "plane"],
  archive: ["old", "box", "storage", "past"],
  atom: ["science", "physics"],
  bird: ["animal", "nature", "twitter"],
  book: ["read", "library", "novel"],
  "book-open": ["read", "reading", "study"],
  bookmark: ["save", "saved", "read later", "favourite"],
  brain: ["mind", "think", "psychology", "learn"],
  briefcase: ["work", "job", "career", "office", "business"],
  calendar: ["date", "day", "daily", "schedule", "journal"],
  camera: ["photo", "picture", "photography"],
  car: ["drive", "vehicle", "auto", "transport"],
  chart: ["data", "stats", "graph", "analytics", "finance"],
  checklist: ["tasks", "todo", "to-do", "list", "done"],
  chef: ["cook", "kitchen", "food", "recipe"],
  "chef-hat": ["cook", "kitchen", "food", "recipe", "meal"],
  code: ["programming", "dev", "software"],
  coins: ["money", "finance", "budget", "cash", "price"],
  compass: ["direction", "explore", "navigate"],
  copy: ["template", "duplicate", "clone"],
  crown: ["king", "royal", "best", "goals"],
  dna: ["biology", "genetics", "science"],
  dumbbell: ["fitness", "gym", "exercise", "sport", "workout", "training"],
  "film-roll": ["movie", "film", "cinema", "video"],
  fire: ["hot", "urgent", "burn", "popular"],
  flash: ["quick", "fast", "energy", "lightning"],
  folder: ["general", "files", "default"],
  "folder-library": ["projects", "collection", "files"],
  game: ["games", "play", "gaming", "controller"],
  ghost: ["spooky", "ideas", "limbo"],
  globe: ["world", "web", "internet", "travel", "languages"],
  graduation: ["school", "university", "degree", "study", "education"],
  health: ["medical", "wellness", "heart rate", "doctor"],
  heart: ["love", "favourite", "like", "family", "health"],
  home: ["house", "family", "living"],
  hourglass: ["time", "later", "wait", "someday", "limbo"],
  idea: ["thought", "inspiration", "lightbulb", "brainstorm"],
  image: ["photo", "picture", "gallery", "screenshot"],
  key: ["secret", "access", "password"],
  lamp: ["light", "ideas", "reading"],
  leaf: ["nature", "garden", "plants", "green"],
  location: ["place", "places", "map", "pin", "address", "where"],
  mail: ["email", "letters", "inbox", "message"],
  mic: ["podcast", "audio", "voice", "interview", "speech"],
  moon: ["night", "sleep", "dream", "dreams"],
  music: ["song", "songs", "audio", "playlist"],
  notebook: ["journal", "diary", "notes", "writing", "log"],
  paintbrush: ["art", "paint", "design", "draw"],
  "paintbrush-2": ["art", "paint", "drawings", "draw", "design"],
  paw: ["pet", "pets", "dog", "cat", "animal"],
  pen: ["write", "writing", "edit", "author"],
  "pencil-edit": ["write", "writing", "draft", "edit"],
  plant: ["garden", "gardening", "grow", "nature"],
  quote: ["quotes", "saying", "citation", "words"],
  rocket: ["launch", "startup", "space", "goals"],
  school: ["class", "classes", "university", "course", "education", "learning"],
  shield: ["security", "safe", "protect", "privacy"],
  "source-code": ["code", "programming", "dev", "software"],
  star: ["favourite", "best", "rating", "important"],
  stethoscope: ["doctor", "medical", "health"],
  sun: ["day", "morning", "weather", "summer"],
  telescope: ["astronomy", "space", "research", "explore"],
  user: ["person", "people", "profile", "contact"],
  users: ["people", "contacts", "friends", "family", "team", "group"],
  video: ["film", "movie", "youtube", "clips", "recording"],
  wallet: ["money", "finance", "budget", "payments", "bank"],
  wrench: ["tools", "fix", "repair", "maintenance", "settings"],
}

/** How well `query` matches `name`: 0 is the best (the name starts with it), larger is worse, `null` is no match. */
function rank(name: string, query: string): number | null {
  if (name.startsWith(query)) return 0
  if (name.includes(query)) return 1
  const words = KEYWORDS[name] ?? []
  if (words.some((w) => w.startsWith(query))) return 2
  if (words.some((w) => w.includes(query))) return 3
  return null
}

/** The names in the icon set that match what was typed, best first and alphabetical among equals. Every name for an
 *  empty query. */
export function searchIcons(query: string): string[] {
  const typed = query.trim().toLowerCase()
  const names = Object.keys(ICON_SET).sort()
  if (!typed) return names
  return names
    .map((name) => ({ name, score: rank(name, typed) }))
    .filter((hit): hit is { name: string; score: number } => hit.score !== null)
    .sort((a, b) => a.score - b.score)
    .map((hit) => hit.name)
}
