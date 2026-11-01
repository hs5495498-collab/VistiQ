import { useMemo, useState, type ComponentType } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  AlertTriangle,
  Briefcase,
  Check,
  Coffee,
  Heart,
  Layers,
  Lightbulb,
  Loader2,
  Martini,
  Package,
  Pin,
  PinOff,
  Ruler,
  Shirt,
  Snowflake,
  Sparkles,
  Sun,
  Umbrella,
  Wind,
  X,
} from 'lucide-react'
import GarmentImage from '../components/GarmentImage'
import { COLOR_OPTIONS, LIGHT_COLOR_NAMES } from '../constants/wardrobeOptions'
import { useWardrobe } from '../hooks/useWardrobe'
import { ApiError, getRecommendation } from '../services/api'
import type { ClothingItem } from '../types/clothing'

// Fixed order so the composition summary always shows all 6 VISTIQ
// categories (even at 0) rather than only whichever ones happen to be
// present — that's the point of the summary: surfacing gaps like
// "Outerwear: 3, everything else: 0" at a glance.
const VISTIQ_CATEGORIES = ['Tops', 'Bottoms', 'Outerwear', 'Footwear', 'Accessories', 'Dresses']

interface OccasionOption {
  value: string
  subtitle: string
  icon: ComponentType<{ size?: number; className?: string }>
}

const OCCASION_OPTIONS: OccasionOption[] = [
  { value: 'Casual', subtitle: 'Coffee, errands, unwind', icon: Coffee },
  { value: 'Work / Studio', subtitle: 'Meetings, creative lab', icon: Briefcase },
  { value: 'Night Out', subtitle: 'Dinner, cocktail lounge', icon: Martini },
]

interface MoodOption {
  value: string
  label: string
  subtitle: string
  icon: ComponentType<{ size?: number; className?: string }>
}

const MOOD_OPTIONS: MoodOption[] = [
  { value: 'Minimal', label: 'Minimalist', subtitle: 'Clean lines', icon: Ruler },
  { value: 'Streetwear', label: 'Streetwear', subtitle: 'Relaxed volumes', icon: Layers },
  { value: 'Smart Casual', label: 'Smart Casual', subtitle: 'Tailored comfort', icon: Shirt },
]

interface WeatherOption {
  value: string
  subtitle: string
  icon: ComponentType<{ size?: number; className?: string }>
}

const WEATHER_OPTIONS: WeatherOption[] = [
  { value: 'Warm', subtitle: '20°C and up', icon: Sun },
  { value: 'Cool', subtitle: '14–19°C', icon: Wind },
  { value: 'Cold', subtitle: 'Below 14°C', icon: Snowflake },
  { value: 'Rainy', subtitle: 'Precipitation', icon: Umbrella },
]

export default function AIStylist() {
  const navigate = useNavigate()
  const { items: wardrobeItems, loading: wardrobeLoading, error: wardrobeError, refetch } = useWardrobe()

  const [occasion, setOccasion] = useState<string | null>(null)
  const [mood, setMood] = useState<string | null>(null)
  const [weather, setWeather] = useState<string | null>(null)
  const [selectedItemIds, setSelectedItemIds] = useState<Set<ClothingItem['id']>>(new Set())
  const [anchorItemId, setAnchorItemId] = useState<ClothingItem['id'] | null>(null)
  const [poolInitialized, setPoolInitialized] = useState(false)

  // Phase 3: optional personalization — request-scoped only, nothing
  // persisted. All default to "no preference", reproducing exactly the
  // pre-Phase-3 request when left untouched.
  const [preferredColors, setPreferredColors] = useState<string[]>([])
  const [avoidedColors, setAvoidedColors] = useState<string[]>([])
  const [preferFavorites, setPreferFavorites] = useState(false)
  const [occasionError, setOccasionError] = useState<string | null>(null)
  const [generating, setGenerating] = useState(false)
  const [generateError, setGenerateError] = useState<string | null>(null)

  // Default the wardrobe pool to "everything included" once the real
  // wardrobe has loaded — only once, so it doesn't stomp on the user's own
  // toggles afterwards. This is a synchronous derivation from already-loaded
  // data, so it's done during render (React's "adjust state during render"
  // pattern) rather than in an effect.
  if (!wardrobeLoading && !poolInitialized && wardrobeItems.length > 0) {
    setPoolInitialized(true)
    setSelectedItemIds(new Set(wardrobeItems.map((item) => item.id)))
  }

  const matchingCount = useMemo(
    () => (mood ? wardrobeItems.filter((item) => item.style === mood).length : null),
    [mood, wardrobeItems],
  )

  // Real counts from the loaded wardrobe — helps explain up front why a
  // recommendation might come back empty (e.g. everything is Outerwear)
  // instead of that only becoming visible after a failed Generate attempt.
  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = Object.fromEntries(VISTIQ_CATEGORIES.map((c) => [c, 0]))
    for (const item of wardrobeItems) {
      counts[item.category] = (counts[item.category] ?? 0) + 1
    }
    return counts
  }, [wardrobeItems])

  function toggleItem(id: ClothingItem['id']) {
    setSelectedItemIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
    // An anchor must always be part of the pool it's anchoring — removing
    // it from the pool clears the anchor rather than leaving it pointing at
    // an item that's no longer being considered.
    setAnchorItemId((current) => (current === id ? null : current))
  }

  function toggleAnchor(id: ClothingItem['id']) {
    setAnchorItemId((current) => (current === id ? null : id))
    // Anchoring an item implies including it in the pool too.
    setSelectedItemIds((prev) => (prev.has(id) ? prev : new Set(prev).add(id)))
  }

  function togglePreferredColor(colorName: string) {
    setPreferredColors((prev) => (prev.includes(colorName) ? prev.filter((c) => c !== colorName) : [...prev, colorName]))
    // A color can't be both preferred and avoided at once.
    setAvoidedColors((prev) => prev.filter((c) => c !== colorName))
  }

  function toggleAvoidedColor(colorName: string) {
    setAvoidedColors((prev) => (prev.includes(colorName) ? prev.filter((c) => c !== colorName) : [...prev, colorName]))
    setPreferredColors((prev) => prev.filter((c) => c !== colorName))
  }

  async function handleGenerate() {
    if (!occasion) {
      setOccasionError("Select what you're dressing for to continue.")
      return
    }
    setOccasionError(null)
    setGenerateError(null)
    setGenerating(true)

    try {
      const response = await getRecommendation({
        occasion,
        style: mood,
        weather,
        wardrobeItemIds: Array.from(selectedItemIds),
        selectedItemId: anchorItemId ?? undefined,
        preferredColors: preferredColors.length > 0 ? preferredColors : undefined,
        avoidedColors: avoidedColors.length > 0 ? avoidedColors : undefined,
        preferFavorites: preferFavorites || undefined,
      })
      // The /recommend response only echoes id/name/category/color/style per
      // outfit item (no image field) — pass the already-loaded real wardrobe
      // items along so Recommendations can look up each item's real photo
      // by id itself, with no backend change required.
      navigate('/recommendations', { state: { recommendationResponse: response, wardrobeItems } })
    } catch (err) {
      setGenerateError(
        err instanceof ApiError
          ? err.message
          : 'Unable to generate recommendations. Make sure the VISTIQ backend is running.',
      )
    } finally {
      setGenerating(false)
    }
  }

  return (
    <section className="mx-auto max-w-6xl px-6 py-10">
      <div className="mb-6 flex flex-col justify-between gap-3 md:flex-row md:items-end">
        <div className="max-w-xl">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-canvas px-3 py-1 font-label-sm text-label-sm uppercase tracking-wider text-secondary">
            <Sparkles size={14} aria-hidden="true" />
            Intelligent Curation Engine
          </span>
          <h1 className="mt-2 font-heading text-h1 text-primary">What are you dressing for?</h1>
          <p className="mt-1 font-body text-body text-secondary">
            Select your plans and mood. VistiQ pairs your wardrobe items into a cohesive look.
          </p>
        </div>
        <div className="flex items-center gap-2 self-start rounded-full bg-surface px-4 py-2 shadow-sm md:self-auto">
          <span className="h-2 w-2 rounded-full bg-secondary" aria-hidden="true" />
          <span className="font-label text-label-sm font-medium text-primary">
            {wardrobeLoading ? 'Syncing garments...' : `${wardrobeItems.length} garments synced`}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-12">
        <section className="flex flex-col gap-6 rounded-2xl bg-surface p-4 shadow-sm md:p-6 lg:col-span-7">
          <fieldset className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <legend className="font-label-sm text-label-sm font-semibold uppercase tracking-wider text-secondary">
                01. What&apos;s the occasion?
              </legend>
              <span className="font-label-sm text-label-sm text-secondary">Required</span>
            </div>
            <div className="mt-1 grid grid-cols-1 gap-2 sm:grid-cols-3">
              {OCCASION_OPTIONS.map(({ value, subtitle, icon: Icon }) => {
                const active = occasion === value
                return (
                  <button
                    key={value}
                    type="button"
                    onClick={() => {
                      setOccasion(value)
                      setOccasionError(null)
                    }}
                    aria-pressed={active}
                    className={`relative flex flex-col items-start rounded-xl p-4 text-left transition-all duration-200 ${
                      active ? 'bg-primary text-on-primary shadow-sm' : 'bg-canvas text-primary hover:bg-border'
                    }`}
                  >
                    <Icon size={22} className={`mb-2 ${active ? 'text-on-primary' : 'text-secondary'}`} />
                    <span className="font-heading text-h3 font-semibold">{value}</span>
                    <span className={`mt-0.5 font-body text-body-sm ${active ? 'opacity-80' : 'text-secondary'}`}>
                      {subtitle}
                    </span>
                  </button>
                )
              })}
            </div>
            {occasionError && (
              <p role="alert" className="font-body text-body-sm text-red-600">
                {occasionError}
              </p>
            )}
          </fieldset>

          <fieldset className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <legend className="font-label-sm text-label-sm font-semibold uppercase tracking-wider text-secondary">
                02. Choose your style preference
              </legend>
              <span className="font-label-sm text-label-sm text-secondary">Optional</span>
            </div>
            <div className="mt-1 grid grid-cols-1 gap-2 sm:grid-cols-3">
              {MOOD_OPTIONS.map(({ value, label, subtitle, icon: Icon }) => {
                const active = mood === value
                return (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setMood(active ? null : value)}
                    aria-pressed={active}
                    className={`flex items-center gap-2 rounded-xl p-2.5 text-left transition-all duration-200 ${
                      active ? 'bg-primary text-on-primary shadow-sm' : 'bg-canvas text-primary hover:bg-border'
                    }`}
                  >
                    <span
                      className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${
                        active ? 'bg-on-primary/10' : 'bg-surface'
                      }`}
                    >
                      <Icon size={18} className={active ? 'text-on-primary' : 'text-secondary'} />
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate font-label text-label font-semibold">{label}</span>
                      <span className={`block truncate font-body text-body-sm ${active ? 'opacity-75' : 'text-secondary'}`}>
                        {subtitle}
                      </span>
                    </span>
                  </button>
                )
              })}
            </div>
          </fieldset>

          <fieldset className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <legend className="font-label-sm text-label-sm font-semibold uppercase tracking-wider text-secondary">
                03. Current weather
              </legend>
              <span className="font-label-sm text-label-sm text-secondary">Optional</span>
            </div>
            <div className="mt-1 grid grid-cols-2 gap-2 sm:grid-cols-4">
              {WEATHER_OPTIONS.map(({ value, subtitle, icon: Icon }) => {
                const active = weather === value
                return (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setWeather(active ? null : value)}
                    aria-pressed={active}
                    className={`flex flex-col items-center justify-center rounded-xl p-2.5 text-center transition-all duration-200 ${
                      active ? 'bg-primary text-on-primary shadow-sm' : 'bg-canvas text-primary hover:bg-border'
                    }`}
                  >
                    <Icon size={22} className={`mb-1 ${active ? 'text-on-primary' : 'text-secondary'}`} />
                    <span className="font-label text-label-sm font-semibold">{value}</span>
                    <span className={`font-body text-body-sm ${active ? 'opacity-80' : 'text-secondary'}`}>
                      {subtitle}
                    </span>
                  </button>
                )
              })}
            </div>
          </fieldset>

          <fieldset className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <legend className="font-label-sm text-label-sm font-semibold uppercase tracking-wider text-secondary">
                04. Personalize (optional)
              </legend>
              <span className="font-label-sm text-label-sm text-secondary">Optional</span>
            </div>

            <div className="flex flex-col gap-1.5">
              <p className="font-body text-body-sm text-secondary">
                Prefer a color — tap again to avoid it instead.
              </p>
              <div className="flex flex-wrap items-center gap-2">
                {COLOR_OPTIONS.map(({ name: colorName, swatch }) => {
                  const preferred = preferredColors.includes(colorName)
                  const avoided = avoidedColors.includes(colorName)
                  return (
                    <button
                      key={colorName}
                      type="button"
                      onClick={() => togglePreferredColor(colorName)}
                      onContextMenu={(event) => {
                        event.preventDefault()
                        toggleAvoidedColor(colorName)
                      }}
                      aria-pressed={preferred}
                      aria-label={`${preferred ? 'Stop preferring' : avoided ? 'Stop avoiding' : 'Prefer'} ${colorName}`}
                      title={`${colorName} — click to prefer, right-click to avoid`}
                      style={{ backgroundColor: swatch }}
                      className={`relative flex h-8 w-8 items-center justify-center rounded-full border border-border transition-transform hover:scale-110 ${
                        preferred ? 'scale-110 ring-2 ring-primary ring-offset-2' : avoided ? 'scale-110 ring-2 ring-red-500 ring-offset-2' : ''
                      }`}
                    >
                      {preferred && (
                        <Check size={14} strokeWidth={3} className={LIGHT_COLOR_NAMES.has(colorName) ? 'text-primary' : 'text-white'} aria-hidden="true" />
                      )}
                      {avoided && (
                        <X size={14} strokeWidth={3} className={LIGHT_COLOR_NAMES.has(colorName) ? 'text-primary' : 'text-white'} aria-hidden="true" />
                      )}
                    </button>
                  )
                })}
              </div>
              {(preferredColors.length > 0 || avoidedColors.length > 0) && (
                <p className="font-body text-body-sm text-secondary">
                  {preferredColors.length > 0 && <>Preferring: {preferredColors.join(', ')}. </>}
                  {avoidedColors.length > 0 && <>Avoiding: {avoidedColors.join(', ')}.</>}
                </p>
              )}
            </div>

            <button
              type="button"
              onClick={() => setPreferFavorites((prev) => !prev)}
              aria-pressed={preferFavorites}
              className={`mt-1 flex items-center gap-2 self-start rounded-full px-3.5 py-1.5 font-label text-label-sm transition-colors ${
                preferFavorites ? 'bg-primary text-on-primary shadow-sm' : 'bg-canvas text-secondary hover:text-primary'
              }`}
            >
              <Heart size={14} strokeWidth={2.5} className={preferFavorites ? 'fill-current' : ''} aria-hidden="true" />
              Favor my favorite items
              {preferFavorites && <Check size={14} strokeWidth={3} aria-hidden="true" />}
            </button>
          </fieldset>

          <div className="mt-2 flex flex-col items-center gap-2 pt-1">
            <button
              type="button"
              onClick={handleGenerate}
              disabled={generating || wardrobeLoading || wardrobeItems.length === 0}
              className="flex w-full items-center justify-center gap-2 rounded-full bg-primary px-6 py-3.5 font-label text-label font-semibold tracking-wide text-on-primary shadow-md transition-all hover:opacity-90 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {generating ? (
                <>
                  <Loader2 size={20} className="animate-spin" aria-hidden="true" />
                  Generating your outfit...
                </>
              ) : (
                <>
                  <Sparkles size={20} aria-hidden="true" />
                  Generate Outfit Recommendation
                </>
              )}
            </button>
            <p className="flex items-center gap-1.5 font-body text-body-sm text-secondary">
              <Package size={16} className="text-secondary" aria-hidden="true" />
              Will consider {selectedItemIds.size} of {wardrobeItems.length} wardrobe items
            </p>
            {generateError && (
              <p role="alert" className="flex items-center gap-1.5 font-body text-body-sm text-red-600">
                <AlertTriangle size={14} aria-hidden="true" />
                {generateError}
              </p>
            )}
          </div>
        </section>

        <aside className="flex flex-col gap-4 lg:col-span-5">
          <div className="flex flex-col gap-3 rounded-2xl bg-surface p-4 shadow-sm md:p-5">
            <div>
              <div className="flex items-center gap-1.5">
                <h2 className="font-heading text-h3 font-semibold text-primary">Wardrobe Pool</h2>
                <span className="rounded-full bg-canvas px-2 py-0.5 font-label-sm text-label-sm font-semibold text-secondary">
                  {selectedItemIds.size} active
                </span>
              </div>
              <p className="mt-0.5 font-body text-body-sm text-secondary">
                Tap an item to include or leave it out of this recommendation.
              </p>
            </div>

            {wardrobeLoading ? (
              <p className="py-6 text-center font-body text-body-sm text-secondary">Loading your wardrobe...</p>
            ) : wardrobeError ? (
              <div className="flex flex-col items-center gap-2 py-6 text-center">
                <AlertTriangle size={22} className="text-red-500" aria-hidden="true" />
                <p className="font-body text-body-sm text-secondary">{wardrobeError}</p>
                <button
                  type="button"
                  onClick={refetch}
                  className="mt-1 rounded-full bg-canvas px-4 py-1.5 font-label text-label-sm text-primary transition-colors hover:bg-border"
                >
                  Try again
                </button>
              </div>
            ) : wardrobeItems.length === 0 ? (
              <div className="flex flex-col items-center gap-2 py-6 text-center">
                <p className="font-body text-body-sm text-secondary">
                  You haven&apos;t added any clothing yet — add a few items first so VistiQ has something to work
                  with.
                </p>
                <Link
                  to="/add-item"
                  className="mt-1 rounded-full bg-primary px-4 py-1.5 font-label text-label-sm text-on-primary transition-opacity hover:opacity-90"
                >
                  Add Item
                </Link>
              </div>
            ) : (
              <>
                <div className="grid grid-cols-3 gap-1.5 rounded-xl bg-canvas p-2.5 sm:grid-cols-6">
                  {VISTIQ_CATEGORIES.map((category) => (
                    <div key={category} className="flex flex-col items-center rounded-lg bg-surface px-1 py-1.5 text-center">
                      <span className="truncate font-label-sm text-label-sm text-secondary" title={category}>
                        {category}
                      </span>
                      <span
                        className={`font-heading text-h3 ${categoryCounts[category] === 0 ? 'text-secondary' : 'text-primary'}`}
                      >
                        {categoryCounts[category]}
                      </span>
                    </div>
                  ))}
                </div>

                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {wardrobeItems.map((item) => {
                    const active = selectedItemIds.has(item.id)
                    const isAnchor = anchorItemId === item.id
                    const styleMatch = mood ? item.style === mood : false
                    return (
                      <div
                        key={item.id}
                        className={`relative flex items-center gap-2.5 rounded-xl p-2 transition-colors ${
                          active ? 'bg-canvas' : 'bg-canvas/40 opacity-50 hover:opacity-80'
                        } ${isAnchor ? 'ring-2 ring-primary' : ''}`}
                      >
                        <button
                          type="button"
                          onClick={() => toggleItem(item.id)}
                          aria-pressed={active}
                          aria-label={`${active ? 'Remove' : 'Include'} ${item.name} in this recommendation`}
                          className="flex min-w-0 flex-1 items-center gap-2.5 text-left"
                        >
                          <span className="block h-12 w-12 shrink-0 overflow-hidden rounded-lg bg-surface">
                            <GarmentImage src={item.image} alt={item.name} category={item.category} className="h-full w-full object-cover" />
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="block font-label-sm text-label-sm uppercase text-secondary">
                              {item.category}
                            </span>
                            <span className="block truncate font-label text-label-sm font-semibold text-primary">
                              {item.name}
                            </span>
                            <span className="mt-0.5 flex items-center gap-1 font-label-sm text-label-sm text-secondary">
                              <span
                                className={`h-1.5 w-1.5 rounded-full ${active ? 'bg-secondary' : 'bg-border'}`}
                                aria-hidden="true"
                              />
                              {isAnchor
                                ? 'Anchor · always included'
                                : active
                                  ? styleMatch
                                    ? 'Included · style match'
                                    : 'Included'
                                  : 'Not included'}
                            </span>
                          </span>
                        </button>

                        <button
                          type="button"
                          onClick={() => toggleAnchor(item.id)}
                          aria-pressed={isAnchor}
                          aria-label={
                            isAnchor
                              ? `Unpin ${item.name} as the anchor item`
                              : `Anchor this recommendation around ${item.name}`
                          }
                          title={isAnchor ? 'Unpin anchor' : 'Anchor outfit on this item'}
                          className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full transition-colors ${
                            isAnchor ? 'bg-primary text-on-primary' : 'text-secondary hover:bg-border hover:text-primary'
                          }`}
                        >
                          {isAnchor ? (
                            <Pin size={14} strokeWidth={2.5} aria-hidden="true" />
                          ) : (
                            <PinOff size={14} strokeWidth={2} aria-hidden="true" />
                          )}
                        </button>
                      </div>
                    )
                  })}
                </div>

                <div className="rounded-xl bg-canvas p-3">
                  <div className="flex items-center gap-1.5">
                    <Sparkles size={16} className="text-secondary" aria-hidden="true" />
                    <span className="font-label text-label-sm font-semibold text-primary">Selection summary</span>
                  </div>
                  <p className="mt-1 font-body text-body-sm text-secondary">
                    {mood
                      ? `${matchingCount} of ${wardrobeItems.length} wardrobe items are tagged "${mood}".`
                      : 'Choose a style preference to see how many wardrobe items match it.'}{' '}
                    {selectedItemIds.size} item{selectedItemIds.size === 1 ? '' : 's'} will be sent in this request.
                    {anchorItemId != null && (
                      <>
                        {' '}
                        Every recommendation will be built around{' '}
                        <strong className="font-label text-label-sm text-primary">
                          {wardrobeItems.find((item) => item.id === anchorItemId)?.name ?? 'your anchor item'}
                        </strong>
                        .
                      </>
                    )}
                  </p>
                </div>
              </>
            )}
          </div>

          <div className="flex items-start gap-2.5 rounded-2xl bg-surface p-4 shadow-sm">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-canvas text-primary">
              <Lightbulb size={16} aria-hidden="true" />
            </span>
            <div>
              <span className="block font-label-sm text-label-sm font-semibold uppercase text-secondary">
                Stylist note
              </span>
              <p className="mt-0.5 font-body text-body-sm italic text-primary">
                &ldquo;Pairing a structured bottom with a relaxed top creates effortless silhouette
                balance.&rdquo;
              </p>
            </div>
          </div>
        </aside>
      </div>
    </section>
  )
}
