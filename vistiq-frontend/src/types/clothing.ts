export type ClothingCategory =
  | 'Tops'
  | 'Bottoms'
  | 'Outerwear'
  | 'Footwear'
  | 'Accessories'
  | 'Dresses'

export type ClothingStyle =
  | 'Casual'
  | 'Smart Casual'
  | 'Minimal'
  | 'Streetwear'
  | 'Formal'
  | 'Sporty'

export type Occasion = 'College' | 'Casual' | 'Office' | 'Party' | 'Formal' | 'Date'

export type Season = 'All Season' | 'Warm Weather' | 'Cool Weather' | 'Layering Pieces'

export type Weather = 'Hot' | 'Warm' | 'Cool' | 'Cold' | 'Rainy'

export interface ClothingItem {
  id: string | number
  name: string
  category: ClothingCategory | string
  /** More specific cut/type within the category, e.g. "Denim Jacket". */
  subcategory?: string
  color: string
  /** A secondary accent color, if the garment has one. */
  secondaryColor?: string
  style: ClothingStyle | string
  /** e.g. "Unisex", "Men's", "Women's" — optional, backend-provided. */
  gender?: string
  image: string
  occasion?: Occasion[] | string[]
  season?: Season[] | string[]
  /** Short descriptive subtitle, e.g. fabric/cut detail ("Straight-Leg Selvedge"). */
  description?: string
  /** Times the item has been worn/logged — powers "Most/Least Worn" sorting. */
  wearCount?: number
  /** ISO date the item was added to the wardrobe — powers "Recently Added" sorting. */
  addedAt?: string
  /** Persisted server-side (Phase 1) — survives reload, unlike the old
   * frontend-only local state. */
  isFavorite?: boolean
  /** Set once at creation time from a Phase 2 photo analysis (Phase 3) —
   * "high"/"medium"/"low", or absent for items created without one (e.g.
   * manual entry, or anything added before this field existed). Used by
   * the Phase 3 recommendation engine to avoid over-trusting an uncertain
   * color; never fabricated for an item that wasn't analyzed. */
  colorReliability?: 'high' | 'medium' | 'low'
}

/** Response from `POST /analyze-clothing`, mapped from the backend's
 * snake_case wire format by src/services/api.ts. category/confidence come
 * from the trained MobileNetV3 classifier (real ML). color/colorConfidence/
 * secondaryColor/colorHex/colorReliability/pattern/brightnessLevel all come
 * from classical image processing (GrabCut segmentation + K-means color
 * clustering, Phase 2) — NOT machine learning. colorConfidence is a
 * cluster-dominance score (0-1) when that pipeline succeeds, and null when
 * it fell back to the simpler Phase 1 method — never an ML confidence
 * value either way. All of these are suggestions for the user to
 * review/correct, never applied to the form silently. */
export interface ClothingAnalysisResult {
  category: string
  confidence: number
  lowConfidence: boolean
  color: string
  colorConfidence: number | null
  message: string
  /** A second notable garment color, only when it's a genuinely
   * significant share of the image — absent for solid-colored garments. */
  secondaryColor: string | null
  colorHex: string | null
  /** How much to trust `color`/`secondaryColor`: "high" (segmentation
   * succeeded + a dominant cluster), "medium", or "low" (fell back to the
   * simpler Phase 1 heuristic) — surface this as a hedge, not hide it. */
  colorReliability: 'high' | 'medium' | 'low' | null
  segmentationApplied: boolean
  pattern: 'solid' | 'patterned' | 'unknown' | null
  brightnessLevel: 'light' | 'medium' | 'dark' | 'unknown' | null
  /** Non-blocking image-quality warnings (e.g. low resolution, blurry,
   * too dark/bright) — the photo was still accepted and analyzed. */
  qualityWarnings: string[]
}

export interface StylistSelection {
  occasion: Occasion | string
  style: ClothingStyle | string
  weather: Weather | string
}

/** Body sent to `POST /recommend` (translated to the backend's snake_case
 * wire format by src/services/api.ts — components only ever see this shape). */
export interface RecommendationRequest extends Pick<StylistSelection, 'occasion'> {
  style: StylistSelection['style'] | null
  weather: StylistSelection['weather'] | null
  wardrobeItemIds: ClothingItem['id'][]
  selectedItemId?: ClothingItem['id'] | null
  topK?: number
  /** Phase 3 — all optional, request-scoped only (no accounts, nothing
   * persisted server-side). Omitting all of these reproduces the exact
   * pre-Phase-3 request/behavior. */
  preferredColors?: string[]
  avoidedColors?: string[]
  preferFavorites?: boolean
  /** Diversity-aware reranking (Phase 3) — on by default server-side;
   * exposed here only as an opt-out. */
  diversify?: boolean
}

/** A single garment as it appears inside a recommended outfit. The backend's
 * recommendation engine only returns these summary fields, not the full
 * ClothingItem record. */
export interface RecommendedItem {
  id: number
  name: string
  category: string
  color: string
  style: string
}

export interface OutfitRecommendation {
  rank: number
  /** 0-100 compatibility score computed by the backend engine (Phase 3:
   * includes any personalization adjustment — see positiveReasons for
   * what contributed). */
  score: number
  items: RecommendedItem[]
  /** Human-readable explanation generated by the backend from the actual scores. */
  reason: string
  /** Phase 3 — the six weighted dimensions (0-1 each), for anyone who
   * wants the real breakdown behind `score`/`reason` rather than just the
   * prose. */
  dimensionScores: Record<string, number>
  /** Phase 3 — specific, evidence-backed reasons this outfit was
   * recommended. Never generic/invented — each one corresponds to an
   * actual score or request match. */
  positiveReasons: string[]
  /** Phase 3 — honest caveats (e.g. low color-extraction reliability, a
   * partial outfit missing a category) — shown so the outfit is never
   * presented as more certain than it is. */
  caveats: string[]
}

/** Response from `POST /recommend`, mapped from the backend's snake_case
 * wire format by src/services/api.ts. */
export interface RecommendationResponse {
  request: {
    occasion: string
    style: string | null
    weather: string | null
    selectedItemId: number | null
  }
  recommendations: OutfitRecommendation[]
  /** Set by the backend when there are no recommendations (empty/insufficient
   * wardrobe pool) to explain why, instead of an empty list with no context. */
  message: string | null
}
