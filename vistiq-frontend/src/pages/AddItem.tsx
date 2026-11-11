import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, Check, CheckCircle2, Lightbulb, Sparkles } from 'lucide-react'
import UploadDropzone from '../components/UploadDropzone'
import { CATEGORY_OPTIONS, COLOR_OPTIONS, LIGHT_COLOR_NAMES, OCCASION_OPTIONS, SEASON_OPTIONS, STYLE_OPTIONS } from '../constants/wardrobeOptions'
import { useObjectUrl } from '../hooks/useObjectUrl'
import { analyzeClothingImage, ApiError, createWardrobeItem, uploadClothingImage } from '../services/api'
import type { ClothingAnalysisResult, ClothingItem } from '../types/clothing'

interface FormErrors {
  name?: string
  category?: string
  color?: string
  style?: string
  image?: string
}

export default function AddItem() {
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [name, setName] = useState('')
  const [category, setCategory] = useState('')
  const [color, setColor] = useState('')
  const [styles, setStyles] = useState<string[]>([])
  const [occasions, setOccasions] = useState<string[]>([])
  const [season, setSeason] = useState<string>('All Season')
  const [errors, setErrors] = useState<FormErrors>({})
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [createdItem, setCreatedItem] = useState<ClothingItem | null>(null)

  // AI analysis (POST /analyze-clothing) — category + color are suggestions
  // only. They pre-fill the fields below but stay fully user-editable; the
  // color is never treated as "confirmed" (colorConfirmed) until the user
  // actually clicks a swatch, since automatic color extraction is not
  // reliable enough to trust silently (see ml/README.md).
  const [analyzing, setAnalyzing] = useState(false)
  const [analysisResult, setAnalysisResult] = useState<ClothingAnalysisResult | null>(null)
  const [analysisError, setAnalysisError] = useState<string | null>(null)
  const [colorConfirmed, setColorConfirmed] = useState(false)

  const successPreviewUrl = useObjectUrl(createdItem ? imageFile : null)

  async function handleFileChange(file: File | null) {
    setImageFile(file)
    setAnalysisResult(null)
    setAnalysisError(null)
    setColorConfirmed(false)
    if (!file) return

    setAnalyzing(true)
    try {
      const result = await analyzeClothingImage(file)
      setAnalysisResult(result)
      // Pre-fill as suggestions — both remain ordinary editable form fields
      // the user can change before saving.
      setCategory(result.category)
      setColor(result.color)
    } catch (err) {
      setAnalysisError(
        err instanceof ApiError
          ? `AI analysis unavailable (${err.message}). You can still enter details manually.`
          : 'AI analysis unavailable. You can still enter details manually.',
      )
    } finally {
      setAnalyzing(false)
    }
  }

  function selectColor(colorName: string) {
    setColor(colorName)
    setColorConfirmed(true)
  }

  function toggleStyle(style: string) {
    setStyles((prev) => (prev.includes(style) ? prev.filter((s) => s !== style) : [...prev, style]))
  }

  function toggleOccasion(occasion: string) {
    setOccasions((prev) => (prev.includes(occasion) ? prev.filter((o) => o !== occasion) : [...prev, occasion]))
  }

  function resetForm() {
    setImageFile(null)
    setName('')
    setCategory('')
    setColor('')
    setStyles([])
    setOccasions([])
    setSeason('All Season')
    setErrors({})
    setSubmitError(null)
    setCreatedItem(null)
    setAnalyzing(false)
    setAnalysisResult(null)
    setAnalysisError(null)
    setColorConfirmed(false)
  }

  function validate(): FormErrors {
    const next: FormErrors = {}
    if (!name.trim()) next.name = 'Garment name is required.'
    if (!category) next.category = 'Select a category.'
    if (!color) next.color = 'Select a primary color.'
    if (styles.length === 0) next.style = 'Select at least one style.'
    if (!imageFile) next.image = 'Upload a photo of the garment.'
    return next
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const nextErrors = validate()
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0) return

    setSubmitError(null)
    setSubmitting(true)
    try {
      // validate() above requires imageFile to be set, so this is always a
      // real File here. Persist it to backend storage (Stage 16) first so
      // the wardrobe record can reference a real, servable image URL —
      // uploading and wardrobe creation stay separate requests (one file
      // endpoint, one JSON endpoint) rather than merging POST /wardrobe
      // into multipart, so existing JSON-only clients of that endpoint are
      // unaffected.
      const imagePath = imageFile ? await uploadClothingImage(imageFile) : null

      // Style Archetypes lets the user pick several looks, but the backend
      // stores (and scores) a single canonical style — the first selection
      // is used as that canonical value. Occasion, on the other hand, is
      // matched by the recommendation engine as a comma-separated list, so
      // every selected occasion is sent through.
      // Phase 3: persist the Phase 2 analysis's secondary color / color
      // reliability — previously computed and shown to the user, but
      // never actually saved (the wardrobe record only stored `color`).
      // Only trusted when the user kept the AI-suggested primary color —
      // if they picked a different color manually, the previously-detected
      // secondary color no longer necessarily corresponds to it, so it's
      // safer to leave it unset than to save a stale pairing.
      const keptAiColor = analysisResult != null && color === analysisResult.color
      const created = await createWardrobeItem({
        name: name.trim(),
        category,
        color,
        style: styles[0],
        occasion: occasions.length > 0 ? occasions.join(', ') : null,
        season,
        image: imagePath,
        secondaryColor: keptAiColor ? analysisResult.secondaryColor : null,
        colorReliability: keptAiColor ? analysisResult.colorReliability : null,
      })
      setCreatedItem(created)
    } catch (err) {
      setSubmitError(
        err instanceof ApiError
          ? err.message
          : 'Unable to save this item. Make sure the VISTIQ backend is running.',
      )
    } finally {
      setSubmitting(false)
    }
  }

  if (createdItem) {
    return (
      <section className="mx-auto max-w-2xl px-6 py-16 text-center">
        <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-canvas text-primary">
          <CheckCircle2 size={28} aria-hidden="true" />
        </span>
        <h1 className="mt-4 font-heading text-h1 text-primary">{createdItem.name} added</h1>
        <p className="mx-auto mt-3 max-w-md font-body text-body text-secondary">
          Saved to your VistiQ wardrobe. It's now available in My Wardrobe and the AI Stylist.
        </p>

        <div className="mt-8 flex flex-col items-center gap-4 rounded-2xl bg-surface p-6 shadow-sm sm:flex-row sm:items-start sm:text-left">
          {successPreviewUrl && (
            <img
              src={successPreviewUrl}
              alt={`${createdItem.name} preview`}
              className="h-32 w-28 shrink-0 rounded-lg object-cover"
            />
          )}
          <div className="space-y-2">
            <p className="font-heading text-h3 text-primary">{createdItem.name}</p>
            <div className="flex flex-wrap justify-center gap-1.5 sm:justify-start">
              <span className="rounded-md bg-canvas px-2 py-0.5 font-label-sm text-label-sm text-secondary">
                {createdItem.category}
              </span>
              <span className="rounded-md bg-canvas px-2 py-0.5 font-label-sm text-label-sm text-secondary">
                {createdItem.color}
              </span>
              <span className="rounded-md bg-canvas px-2 py-0.5 font-label-sm text-label-sm text-secondary">
                {createdItem.style}
              </span>
              {createdItem.occasion?.map((occasion) => (
                <span key={occasion} className="rounded-md bg-canvas px-2 py-0.5 font-label-sm text-label-sm text-secondary">
                  {occasion}
                </span>
              ))}
              {createdItem.season?.map((season) => (
                <span key={season} className="rounded-md bg-canvas px-2 py-0.5 font-label-sm text-label-sm text-secondary">
                  {season}
                </span>
              ))}
            </div>
          </div>
        </div>

        <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <button
            type="button"
            onClick={resetForm}
            className="rounded-full bg-canvas px-5 py-2.5 font-label text-label-sm text-primary transition-colors hover:bg-border"
          >
            Add another item
          </button>
          <Link
            to="/wardrobe"
            className="rounded-full bg-primary px-5 py-2.5 font-label text-label-sm text-on-primary transition-opacity hover:opacity-90"
          >
            View My Wardrobe
          </Link>
        </div>
      </section>
    )
  }

  return (
    <section className="mx-auto max-w-5xl px-6 py-12">
      <div className="mx-auto max-w-xl text-center">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-canvas px-3.5 py-1 font-label-sm text-label-sm uppercase tracking-wider text-secondary">
          <Sparkles size={14} aria-hidden="true" />
          Wardrobe Intelligence
        </span>
        <h1 className="mt-4 font-heading text-h1 text-primary">Add New Garment</h1>
        <p className="mt-2 font-body text-body text-secondary">
          Upload a clear photo and categorize your piece so it's ready for outfit recommendations.
        </p>
      </div>

      {submitError && (
        <div
          role="alert"
          className="mx-auto mt-6 flex max-w-3xl items-start gap-2.5 rounded-xl bg-red-50 p-4 text-left"
        >
          <AlertTriangle size={18} className="mt-0.5 shrink-0 text-red-600" aria-hidden="true" />
          <p className="font-body text-body-sm text-red-700">{submitError}</p>
        </div>
      )}

      <form
        onSubmit={handleSubmit}
        noValidate
        className="mt-10 flex flex-col gap-8 rounded-2xl bg-surface p-6 shadow-sm md:p-10 lg:flex-row"
      >
        <div className="flex flex-col gap-4 lg:w-[42%]">
          <div className="flex items-center gap-1.5 font-label-sm text-label-sm uppercase tracking-wider text-secondary">
            <Sparkles size={12} aria-hidden="true" />
            AI Clothing Analysis
          </div>
          <UploadDropzone file={imageFile} onFileChange={handleFileChange} error={errors.image} />

          {analyzing && (
            <div className="flex items-center gap-2.5 rounded-lg bg-canvas p-3">
              <Sparkles size={18} className="shrink-0 animate-pulse text-secondary" aria-hidden="true" />
              <p className="font-body text-body-sm text-secondary">Analyzing clothing image…</p>
            </div>
          )}

          {!analyzing && analysisResult && (
            <div
              className={`flex flex-col gap-1 rounded-lg p-3 ${
                analysisResult.lowConfidence ? 'bg-amber-50' : 'bg-canvas'
              }`}
            >
              <div className="flex items-center gap-2">
                <Sparkles
                  size={18}
                  className={analysisResult.lowConfidence ? 'shrink-0 text-amber-600' : 'shrink-0 text-primary'}
                  aria-hidden="true"
                />
                <p className="font-label text-label-sm text-primary">
                  AI prediction: {analysisResult.category} — {Math.round(analysisResult.confidence * 100)}% confidence
                </p>
              </div>
              <p
                className={`font-body text-body-sm ${
                  analysisResult.lowConfidence ? 'text-amber-700' : 'text-secondary'
                }`}
              >
                {analysisResult.message}
              </p>

              {(analysisResult.secondaryColor || analysisResult.colorReliability) && (
                <p className="flex flex-wrap items-center gap-1.5 font-body text-body-sm text-secondary">
                  {analysisResult.secondaryColor && (
                    <span>
                      Secondary color: <span className="font-label text-primary">{analysisResult.secondaryColor}</span>
                    </span>
                  )}
                  {analysisResult.colorReliability && (
                    <span
                      className={`rounded-full px-2 py-0.5 font-label-sm text-label-sm ${
                        analysisResult.colorReliability === 'high'
                          ? 'bg-canvas text-primary'
                          : 'bg-amber-100 text-amber-800'
                      }`}
                    >
                      Color reliability: {analysisResult.colorReliability}
                      {!analysisResult.segmentationApplied && ' (background may have influenced this guess)'}
                    </span>
                  )}
                </p>
              )}

              <p className="font-body text-body-sm text-secondary">
                Category and color below are pre-filled from this prediction — please review and correct them if needed.
              </p>
            </div>
          )}

          {!analyzing && analysisResult && analysisResult.qualityWarnings.length > 0 && (
            <div className="flex items-start gap-2.5 rounded-lg bg-amber-50 p-3">
              <AlertTriangle size={18} className="mt-0.5 shrink-0 text-amber-600" aria-hidden="true" />
              <div className="font-body text-body-sm text-amber-700">
                {analysisResult.qualityWarnings.map((warning) => (
                  <p key={warning}>{warning}</p>
                ))}
              </div>
            </div>
          )}

          {!analyzing && analysisError && (
            <div className="flex items-start gap-2.5 rounded-lg bg-canvas p-3">
              <AlertTriangle size={18} className="mt-0.5 shrink-0 text-secondary" aria-hidden="true" />
              <p className="font-body text-body-sm text-secondary">{analysisError}</p>
            </div>
          )}

          <div className="flex items-start gap-2.5 rounded-lg bg-canvas p-3">
            <Lightbulb size={20} className="mt-0.5 shrink-0 text-secondary" aria-hidden="true" />
            <p className="font-body text-body-sm text-secondary">
              <strong className="font-label text-label text-primary">Styling tip: </strong>
              flat-lay photos on a plain, non-reflective background give the clearest color and silhouette read.
            </p>
          </div>

          {category === 'Dresses' && (
            <div className="flex items-start gap-2.5 rounded-lg bg-canvas p-3">
              <Lightbulb size={20} className="mt-0.5 shrink-0 text-secondary" aria-hidden="true" />
              <p className="font-body text-body-sm text-secondary">
                <strong className="font-label text-label text-primary">For dresses: </strong>
                frame the full garment from shoulder to hem. A photo cropped to just part of the dress (e.g. only
                the bodice) can be misread as a top, and Virtual Try-On will only recreate the visible portion.
              </p>
            </div>
          )}
        </div>

        <div className="flex flex-col gap-6 lg:w-[58%]">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="garment-name" className="flex items-center justify-between font-label text-label text-primary">
              <span>Garment Name</span>
              <span className="font-body text-body-sm font-normal text-secondary">Required</span>
            </label>
            <input
              id="garment-name"
              type="text"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="e.g. Vintage Denim Jacket"
              aria-invalid={Boolean(errors.name)}
              aria-describedby={errors.name ? 'garment-name-error' : undefined}
              className="h-11 rounded-lg bg-canvas px-4 font-body text-body text-primary placeholder:text-secondary focus:bg-surface focus:shadow-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
            />
            {errors.name && (
              <p id="garment-name-error" role="alert" className="font-body text-body-sm text-red-600">
                {errors.name}
              </p>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="garment-category" className="flex items-center justify-between font-label text-label text-primary">
              <span>Category</span>
              {analysisResult && category === analysisResult.category && (
                <span className="font-body text-body-sm font-normal text-secondary">AI predicted — please review</span>
              )}
            </label>
            <select
              id="garment-category"
              value={category}
              onChange={(event) => setCategory(event.target.value)}
              aria-invalid={Boolean(errors.category)}
              aria-describedby={errors.category ? 'garment-category-error' : undefined}
              className="h-11 cursor-pointer rounded-lg bg-canvas px-4 font-body text-body text-primary focus:bg-surface focus:shadow-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
            >
              <option value="" disabled>
                Select a category
              </option>
              {CATEGORY_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
            {errors.category && (
              <p id="garment-category-error" role="alert" className="font-body text-body-sm text-red-600">
                {errors.category}
              </p>
            )}
          </div>

          <fieldset className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <legend className="font-label text-label text-primary">Primary Color</legend>
              <span className="font-label-sm text-label-sm font-medium text-secondary">
                {color && analysisResult && color === analysisResult.color && !colorConfirmed
                  ? `Suggested color — please confirm: ${color}`
                  : color
                    ? `Selected: ${color}`
                    : 'None selected'}
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-3 py-1">
              {COLOR_OPTIONS.map(({ name: colorName, swatch }) => {
                const active = color === colorName
                return (
                  <button
                    key={colorName}
                    type="button"
                    onClick={() => selectColor(colorName)}
                    aria-pressed={active}
                    aria-label={`Select ${colorName}`}
                    style={{ backgroundColor: swatch }}
                    className={`flex h-8 w-8 items-center justify-center rounded-full border border-border transition-transform hover:scale-110 ${
                      active ? 'scale-110 shadow-md ring-2 ring-primary ring-offset-2' : ''
                    }`}
                  >
                    {active && (
                      <Check
                        size={14}
                        strokeWidth={3}
                        className={LIGHT_COLOR_NAMES.has(colorName) ? 'text-primary' : 'text-white'}
                        aria-hidden="true"
                      />
                    )}
                  </button>
                )
              })}
            </div>
            {errors.color && (
              <p role="alert" className="font-body text-body-sm text-red-600">
                {errors.color}
              </p>
            )}
          </fieldset>

          <fieldset className="flex flex-col gap-2">
            <legend className="font-label text-label text-primary">
              Style Archetypes <span className="font-body text-body-sm font-normal text-secondary">(select all that apply)</span>
            </legend>
            <div className="flex flex-wrap gap-1.5">
              {STYLE_OPTIONS.map((style) => {
                const active = styles.includes(style)
                return (
                  <button
                    key={style}
                    type="button"
                    onClick={() => toggleStyle(style)}
                    aria-pressed={active}
                    className={`flex items-center gap-1 rounded-full px-3.5 py-1.5 font-label text-label-sm transition-colors ${
                      active ? 'bg-primary text-on-primary shadow-sm' : 'bg-canvas text-secondary hover:text-primary'
                    }`}
                  >
                    {style}
                    {active && <Check size={14} strokeWidth={3} aria-hidden="true" />}
                  </button>
                )
              })}
            </div>
            {errors.style && (
              <p role="alert" className="font-body text-body-sm text-red-600">
                {errors.style}
              </p>
            )}
          </fieldset>

          <fieldset className="flex flex-col gap-2">
            <legend className="font-label text-label text-primary">
              Occasion <span className="font-body text-body-sm font-normal text-secondary">(optional)</span>
            </legend>
            <div className="flex flex-wrap gap-1.5">
              {OCCASION_OPTIONS.map((occasion) => {
                const active = occasions.includes(occasion)
                return (
                  <button
                    key={occasion}
                    type="button"
                    onClick={() => toggleOccasion(occasion)}
                    aria-pressed={active}
                    className={`flex items-center gap-1 rounded-full px-3.5 py-1.5 font-label text-label-sm transition-colors ${
                      active ? 'bg-primary text-on-primary shadow-sm' : 'bg-canvas text-secondary hover:text-primary'
                    }`}
                  >
                    {occasion}
                    {active && <Check size={14} strokeWidth={3} aria-hidden="true" />}
                  </button>
                )
              })}
            </div>
          </fieldset>

          <fieldset className="flex flex-col gap-2">
            <legend className="font-label text-label text-primary">Weather Season</legend>
            <div className="grid grid-cols-2 gap-1 rounded-xl bg-canvas p-1 sm:grid-cols-4">
              {SEASON_OPTIONS.map((option) => {
                const active = season === option
                return (
                  <button
                    key={option}
                    type="button"
                    onClick={() => setSeason(option)}
                    aria-pressed={active}
                    className={`rounded-lg px-2 py-2 text-center font-label text-label-sm transition-all ${
                      active ? 'bg-surface font-semibold text-primary shadow-sm' : 'text-secondary hover:text-primary'
                    }`}
                  >
                    {option}
                  </button>
                )
              })}
            </div>
          </fieldset>

          <div className="flex flex-col gap-2 pt-2">
            <button
              type="submit"
              disabled={submitting}
              className="flex w-full items-center justify-center gap-1.5 rounded-full bg-primary px-6 py-3.5 font-label text-label text-on-primary shadow-sm transition-all hover:opacity-90 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60"
            >
              <CheckCircle2 size={20} aria-hidden="true" />
              {submitting ? 'Saving...' : 'Save to Wardrobe'}
            </button>
            <button
              type="button"
              onClick={resetForm}
              disabled={submitting}
              className="w-full py-2 text-center font-label text-label-sm text-secondary transition-colors hover:text-primary disabled:cursor-not-allowed disabled:opacity-60"
            >
              Cancel &amp; Discard
            </button>
          </div>
        </div>
      </form>
    </section>
  )
}
