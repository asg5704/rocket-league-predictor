const BASE = '/api'

export interface Player {
  player_id: string
  display_name: string
  archetype: string
  team_name: string | null
  elo: number
}

export interface PlayersResponse {
  players: Player[]
  total: number
}

export interface Weights {
  synergy: number
  archetype: number
  elo: number
}

export interface LineupPlayer {
  player_id: string
  display_name: string
  archetype: string
}

export interface Lineup {
  rank: number
  players: LineupPlayer[]
  score: number
  synergy: number
  archetype_combo: string
  archetype_bonus: number
  mean_elo: number
  n_matches: number
  low_sample: boolean
}

export interface OptimizeResponse {
  lineups: Lineup[]
  pool_size: number
}

export interface EloRating {
  rank: number
  team_name: string
  elo: number
  country: string | null
  roster: string[]
}

export interface EloRatingsResponse {
  ratings: EloRating[]
  total: number
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`)
  return res.json()
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error(detail?.detail ?? `POST ${path} → ${res.status}`)
  }
  return res.json()
}

export const api = {
  getPlayers: () => get<PlayersResponse>('/players'),
  getEloRatings: () => get<EloRatingsResponse>('/elo-ratings'),
  optimize: (player_ids: string[], top_k: number, weights: Weights) =>
    post<OptimizeResponse>('/optimize', { player_ids, top_k, weights }),
}
