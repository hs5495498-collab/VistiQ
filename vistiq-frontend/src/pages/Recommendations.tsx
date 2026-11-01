import { useMemo } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Check, Sparkles, Wand2 } from 'lucide-react'
import GarmentImage from '../components/GarmentImage'
import type { ClothingItem, OutfitRecommendation, RecommendationResponse } from '../types/clothing'

interface RecommendationsLocationState {
  recommendationResponse?: RecommendationResponse
  /** The real wardrobe, as already loaded by AI Stylist — /recommend itself
   * only echoes id/name/category/color/style per outfit item, no image, so
   * this is how real photos reach this page without any backend change. */
  wardrobeItems?: ClothingItem[]
}

/** /recommend's `reason` string is generated deterministically from real
 * score thresholds (see app/recommendation/engine.py _generate_explanation)
 * — these patterns mirror its exact phrasing, so a bullet only ever appears
 * when the backend's own sentence actually said so. Category compatibility
 * isn't spelled out in that sentence but is a structural guarantee of every
 * generated outfit (rules.py only ever pairs complementary categories), so
 * it's included unconditionally rather than parsed. */
function explanationPoints(reason: string): string[] {
  const points: string[] = []
  if (/colors? \(.+?\) complement each other/i.test(reason)) points.push('Color compatibility')
  points.push('Compatible clothing categories')
  if (/consistent .+? style/i.test(reason)) points.push('Style compatibility')
  if (/fits the .+? occasion/i.test(reason)) points.push('Occasion suitability')
  if (/suits .+? weather/i.test(reason)) points.push('Weather suitability')
  points.push('Available in your selected wardrobe')
  return points
}

function OutfitCard({ outfit, imageById }: { outfit: OutfitRecommendation; imageById: Map<number, string> }) {
  const points = explanationPoints(outfit.reason)

  return (
    <div className="overflow-hidden rounded-2xl bg-surface shadow-sm">
      <div className="flex items-center justify-between px-5 pt-5 md:px-6 md:pt-6">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-canvas px-3 py-1 font-label text-label-sm text-primary">
          Outfit #{outfit.rank}
        </span>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-primary px-3 py-1 font-label text-label-sm text-on-primary">
          {outfit.score}% Match
        </span>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 px-5 sm:grid-cols-4 md:px-6">
        {outfit.items.map((item) => (
          <div key={item.id} className="flex flex-col overflow-hidden rounded-xl bg-canvas">
            <div className="aspect-[3/4] w-full overflow-hidden">
              <GarmentImage
                src={imageById.get(item.id)}
                alt={item.name}
                category={item.category}
                className="h-full w-full object-cover"
              />
            </div>
            <div className="p-2.5">
              <span className="block font-label-sm text-label-sm uppercase text-secondary">{item.category}</span>
              <span className="block truncate font-heading text-h3 text-[15px] leading-tight text-primary">
                {item.name}
              </span>
              <span className="mt-0.5 block font-body text-body-sm text-[13px] text-secondary">{item.color}</span>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-5 border-t border-border px-5 py-5 md:px-6">
        <p className="font-label text-label text-primary">Why we recommend it</p>
        <ul className="mt-2 grid grid-cols-1 gap-1.5 sm:grid-cols-2">
          {points.map((point) => (
            <li key={point} className="flex items-center gap-1.5 font-body text-body-sm text-secondary">
              <Check size={13} strokeWidth={2.5} className="shrink-0 text-primary" aria-hidden="true" />
              {point}
            </li>
          ))}
        </ul>
        <p className="mt-3 font-body text-body-sm italic leading-relaxed text-secondary">{outfit.reason}</p>
      </div>
    </div>
  )
}

export default function Recommendations() {
  const location = useLocation()
  const state = location.state as RecommendationsLocationState | null
  const response = state?.recommendationResponse ?? null

  const imageById = useMemo(() => {
    const map = new Map<number, string>()
    for (const item of state?.wardrobeItems ?? []) {
      if (item.image) map.set(Number(item.id), item.image)
    }
    return map
  }, [state?.wardrobeItems])

  if (!response) {
    return (
      <section className="mx-auto max-w-2xl px-6 py-20 text-center">
        <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-canvas text-primary">
          <Wand2 size={26} aria-hidden="true" />
        </span>
        <h1 className="mt-4 font-heading text-h1 text-primary">No recommendation request yet</h1>
        <p className="mx-auto mt-3 max-w-md font-body text-body text-secondary">
          Recommendations are built from your AI Stylist selections. Choose an occasion, style, and
          weather there, then come back here.
        </p>
        <Link
          to="/stylist"
          className="mt-6 inline-flex items-center gap-1.5 rounded-full bg-primary px-6 py-3 font-label text-label text-on-primary shadow-sm transition-opacity hover:opacity-90"
        >
          <Sparkles size={18} aria-hidden="true" />
          Go to AI Stylist
        </Link>
      </section>
    )
  }

  const { request, recommendations, message } = response

  return (
    <section className="mx-auto max-w-6xl px-6 py-10">
      <div className="mb-6 flex flex-col gap-1">
        <span className="inline-flex items-center gap-1.5 font-label-sm text-label-sm uppercase tracking-wider text-secondary">
          <span className="h-2 w-2 rounded-full bg-secondary" aria-hidden="true" />
          VistiQ Recommendations
        </span>
        <h1 className="font-heading text-h1 text-primary">Your Outfit Recommendations</h1>
        <p className="flex flex-wrap items-center gap-2 font-body text-body-sm text-secondary">
          <span>Curated for {request.occasion}</span>
          {request.style && (
            <>
              <span className="h-1 w-1 rounded-full bg-border" aria-hidden="true" />
              <span>{request.style}</span>
            </>
          )}
          {request.weather && (
            <>
              <span className="h-1 w-1 rounded-full bg-border" aria-hidden="true" />
              <span>{request.weather} weather</span>
            </>
          )}
        </p>
      </div>

      {recommendations.length === 0 ? (
        <div className="rounded-2xl bg-surface p-10 text-center shadow-sm">
          <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-canvas text-secondary">
            <Wand2 size={22} aria-hidden="true" />
          </span>
          <p className="mt-3 font-heading text-h3 text-primary">No complete outfit found</p>
          <p className="mx-auto mt-2 max-w-md font-body text-body-sm text-secondary">
            {message ??
              'Your selected wardrobe pool does not contain enough compatible categories for this occasion. Add or select items from different categories such as Tops, Bottoms, and Footwear.'}
          </p>
          <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
            <Link
              to="/wardrobe"
              className="inline-flex items-center gap-1.5 rounded-full bg-primary px-5 py-2.5 font-label text-label-sm text-on-primary transition-opacity hover:opacity-90"
            >
              Go to My Wardrobe
            </Link>
            <Link
              to="/stylist"
              className="inline-flex items-center gap-1.5 rounded-full bg-canvas px-5 py-2.5 font-label text-label-sm text-primary transition-colors hover:bg-border"
            >
              <Wand2 size={16} aria-hidden="true" />
              Adjust in AI Stylist
            </Link>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {recommendations.map((outfit) => (
            <OutfitCard key={outfit.rank} outfit={outfit} imageById={imageById} />
          ))}

          <div className="flex justify-center pt-2">
            <Link
              to="/stylist"
              className="inline-flex items-center gap-2 rounded-full bg-surface px-6 py-3 font-label text-label text-primary shadow-sm transition-colors hover:bg-border"
            >
              <Wand2 size={18} aria-hidden="true" />
              Adjust in AI Stylist
            </Link>
          </div>
        </div>
      )}
    </section>
  )
}
