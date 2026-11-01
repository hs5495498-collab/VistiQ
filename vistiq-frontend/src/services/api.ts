/**
 * Centralized VISTIQ backend client.
 *
 * This is the ONLY module that knows the backend's snake_case wire format —
 * every function here accepts/returns the app's own camelCase types
 * (from src/types/clothing.ts) and does the translation internally.
 */

import type { ClothingAnalysisResult, ClothingItem, RecommendationRequest, RecommendationResponse } from '../types/clothing'

const API_BASE_URL: string = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch {
    throw new ApiError('VISTIQ backend is unavailable. Start the FastAPI server and try again.', 0)
  }

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`
    try {
      const body: unknown = await response.json()
      if (body && typeof body === 'object' && 'detail' in body) {
        const raw = (body as { detail: unknown }).detail
        if (typeof raw === 'string') {
          detail = raw
        } else if (Array.isArray(raw)) {
          detail =
            raw
              .map((entry) => (entry && typeof entry === 'object' && 'msg' in entry ? String(entry.msg) : null))
              .filter(Boolean)
              .join('; ') || detail
        }
      }
    } catch {
      // Response body wasn't JSON — keep the generic message.
    }
    throw new ApiError(detail, response.status)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

/** Shared multipart-upload path for endpoints that take a single file
 * (POST /analyze-clothing, POST /wardrobe/images) — no Content-Type header
 * here on purpose, the browser sets the multipart boundary itself, which
 * apiFetch()'s JSON default would break. */
async function multipartFetch<T>(path: string, file: File): Promise<T> {
  const formData = new FormData()
  formData.append('file', file)

  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { method: 'POST', body: formData })
  } catch {
    throw new ApiError('VISTIQ backend is unavailable. Start the FastAPI server and try again.', 0)
  }

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`
    try {
      const body: unknown = await response.json()
      if (body && typeof body === 'object' && 'detail' in body) {
        const raw = (body as { detail: unknown }).detail
        if (typeof raw === 'string') {
          detail = raw
        } else if (Array.isArray(raw)) {
          detail =
            raw
              .map((entry) => (entry && typeof entry === 'object' && 'msg' in entry ? String(entry.msg) : null))
              .filter(Boolean)
              .join('; ') || detail
        }
      }
    } catch {
      // Response body wasn't JSON — keep the generic message.
    }
    throw new ApiError(detail, response.status)
  }

  return (await response.json()) as T
}

/** Resolves a backend-relative image path (e.g. "/uploads/<uuid>.jpg") to a
 * fully-qualified URL the frontend can render. Passes an already-absolute
 * URL through unchanged, in case that's ever what's stored. */
function resolveImageUrl(path: string | null): string {
  if (!path) return ''
  return /^https?:\/\//.test(path) ? path : `${API_BASE_URL}${path}`
}

// ---------------------------------------------------------------------------
// Wardrobe (backend: app/schemas/clothing.py)
// ---------------------------------------------------------------------------

interface ApiClothingItem {
  id: number
  name: string
  category: string
  subcategory: string | null
  color: string
  secondary_color: string | null
  style: string
  occasion: string | null
  season: string | null
  gender: string | null
  image: string | null
  description: string | null
  wear_count: number
  created_at: string
  is_favorite: boolean
}

export interface ClothingItemCreateInput {
  name: string
  category: string
  color: string
  style: string
  subcategory?: string | null
  secondaryColor?: string | null
  occasion?: string | null
  season?: string | null
  gender?: string | null
  image?: string | null
  description?: string | null
  isFavorite?: boolean
}

export type ClothingItemUpdateInput = Partial<ClothingItemCreateInput> & { wearCount?: number }

function mapApiClothingItem(raw: ApiClothingItem): ClothingItem {
  return {
    id: raw.id,
    name: raw.name,
    category: raw.category,
    subcategory: raw.subcategory ?? undefined,
    color: raw.color,
    secondaryColor: raw.secondary_color ?? undefined,
    style: raw.style,
    gender: raw.gender ?? undefined,
    image: resolveImageUrl(raw.image),
    occasion: raw.occasion ? raw.occasion.split(',').map((value) => value.trim()) : undefined,
    season: raw.season ? [raw.season] : undefined,
    description: raw.description ?? undefined,
    wearCount: raw.wear_count,
    addedAt: raw.created_at,
    isFavorite: raw.is_favorite,
  }
}

function toApiCreatePayload(input: ClothingItemCreateInput) {
  return {
    name: input.name,
    category: input.category,
    color: input.color,
    style: input.style,
    subcategory: input.subcategory ?? null,
    secondary_color: input.secondaryColor ?? null,
    occasion: input.occasion ?? null,
    season: input.season ?? null,
    gender: input.gender ?? null,
    image: input.image ?? null,
    description: input.description ?? null,
    is_favorite: input.isFavorite ?? false,
  }
}

function toApiUpdatePayload(input: ClothingItemUpdateInput) {
  const payload: Record<string, unknown> = {}
  if (input.name !== undefined) payload.name = input.name
  if (input.category !== undefined) payload.category = input.category
  if (input.color !== undefined) payload.color = input.color
  if (input.style !== undefined) payload.style = input.style
  if (input.subcategory !== undefined) payload.subcategory = input.subcategory
  if (input.secondaryColor !== undefined) payload.secondary_color = input.secondaryColor
  if (input.occasion !== undefined) payload.occasion = input.occasion
  if (input.season !== undefined) payload.season = input.season
  if (input.gender !== undefined) payload.gender = input.gender
  if (input.image !== undefined) payload.image = input.image
  if (input.description !== undefined) payload.description = input.description
  if (input.wearCount !== undefined) payload.wear_count = input.wearCount
  if (input.isFavorite !== undefined) payload.is_favorite = input.isFavorite
  return payload
}

export async function getWardrobe(): Promise<ClothingItem[]> {
  const items = await apiFetch<ApiClothingItem[]>('/wardrobe')
  return items.map(mapApiClothingItem)
}

export async function createWardrobeItem(input: ClothingItemCreateInput): Promise<ClothingItem> {
  const created = await apiFetch<ApiClothingItem>('/wardrobe', {
    method: 'POST',
    body: JSON.stringify(toApiCreatePayload(input)),
  })
  return mapApiClothingItem(created)
}

export async function updateWardrobeItem(
  id: ClothingItem['id'],
  input: ClothingItemUpdateInput,
): Promise<ClothingItem> {
  const updated = await apiFetch<ApiClothingItem>(`/wardrobe/${id}`, {
    method: 'PUT',
    body: JSON.stringify(toApiUpdatePayload(input)),
  })
  return mapApiClothingItem(updated)
}

export async function deleteWardrobeItem(id: ClothingItem['id']): Promise<void> {
  await apiFetch<{ message: string }>(`/wardrobe/${id}`, { method: 'DELETE' })
}

// ---------------------------------------------------------------------------
// Recommendations (backend: app/schemas/recommendation.py)
// ---------------------------------------------------------------------------

interface ApiRecommendedItem {
  id: number
  name: string
  category: string
  color: string
  style: string
}

interface ApiOutfitRecommendation {
  rank: number
  score: number
  items: ApiRecommendedItem[]
  reason: string
}

interface ApiRecommendationResponse {
  request: {
    occasion: string
    style: string | null
    weather: string | null
    selected_item_id: number | null
  }
  recommendations: ApiOutfitRecommendation[]
  message: string | null
}

export async function getRecommendation(request: RecommendationRequest): Promise<RecommendationResponse> {
  const payload = {
    occasion: request.occasion,
    style: request.style ?? null,
    weather: request.weather ?? null,
    wardrobe_item_ids: request.wardrobeItemIds.map(Number),
    selected_item_id: request.selectedItemId != null ? Number(request.selectedItemId) : null,
    top_k: request.topK,
  }

  const raw = await apiFetch<ApiRecommendationResponse>('/recommend', {
    method: 'POST',
    body: JSON.stringify(payload),
  })

  return {
    request: {
      occasion: raw.request.occasion,
      style: raw.request.style,
      weather: raw.request.weather,
      selectedItemId: raw.request.selected_item_id,
    },
    recommendations: raw.recommendations,
    message: raw.message,
  }
}

// ---------------------------------------------------------------------------
// ML clothing analysis (backend: app/schemas/clothing_analysis.py)
// ---------------------------------------------------------------------------

interface ApiClothingAnalysisResponse {
  category: string
  confidence: number
  low_confidence: boolean
  color: string
  color_confidence: number | null
  message: string
}

/** Uploads a photo to POST /analyze-clothing for a real MobileNetV3
 * category prediction + deterministic dominant-color suggestion. Both are
 * suggestions only — the caller must let the user review/correct them
 * before saving, never apply them to a wardrobe record silently. Throws
 * ApiError with status 503 if no trained model is available on the backend. */
export async function analyzeClothingImage(file: File): Promise<ClothingAnalysisResult> {
  const raw = await multipartFetch<ApiClothingAnalysisResponse>('/analyze-clothing', file)
  return {
    category: raw.category,
    confidence: raw.confidence,
    lowConfidence: raw.low_confidence,
    color: raw.color,
    colorConfidence: raw.color_confidence,
    message: raw.message,
  }
}

// ---------------------------------------------------------------------------
// Wardrobe image upload (backend: app/routes/wardrobe.py POST /wardrobe/images)
// ---------------------------------------------------------------------------

/** Uploads a photo to POST /wardrobe/images for local persistent storage,
 * returning the relative URL to pass as the `image` field on a subsequent
 * createWardrobeItem/updateWardrobeItem call. Separate from
 * analyzeClothingImage — one endpoint predicts, this one persists; Add Item
 * calls both against the same File the user picked. */
export async function uploadClothingImage(file: File): Promise<string> {
  const raw = await multipartFetch<{ image: string }>('/wardrobe/images', file)
  return raw.image
}
