import { useState, type FormEvent } from 'react'
import { AlertTriangle, Check, Loader2 } from 'lucide-react'
import GarmentImage from './GarmentImage'
import Modal from './Modal'
import UploadDropzone from './UploadDropzone'
import { CATEGORY_OPTIONS, COLOR_OPTIONS, LIGHT_COLOR_NAMES, OCCASION_OPTIONS, SEASON_OPTIONS, STYLE_OPTIONS } from '../constants/wardrobeOptions'
import { ApiError, updateWardrobeItem, uploadClothingImage } from '../services/api'
import type { ClothingItem } from '../types/clothing'

interface EditItemModalProps {
  item: ClothingItem
  onClose: () => void
  /** Called only with the server-confirmed updated record after a
   * successful PUT /wardrobe/{id}. */
  onSaved: (updated: ClothingItem) => void
}

interface FormErrors {
  name?: string
  category?: string
  color?: string
  style?: string
}

export default function EditItemModal({ item, onClose, onSaved }: EditItemModalProps) {
  const [name, setName] = useState(item.name)
  const [category, setCategory] = useState(item.category)
  const [color, setColor] = useState(item.color)
  const [style, setStyle] = useState(item.style)
  const [occasions, setOccasions] = useState<string[]>(item.occasion ?? [])
  const [season, setSeason] = useState(item.season?.[0] ?? 'All Season')
  const [description, setDescription] = useState(item.description ?? '')

  const [replacingPhoto, setReplacingPhoto] = useState(false)
  const [newImageFile, setNewImageFile] = useState<File | null>(null)

  const [errors, setErrors] = useState<FormErrors>({})
  const [saving, setSaving] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  function toggleOccasion(occasion: string) {
    setOccasions((prev) => (prev.includes(occasion) ? prev.filter((o) => o !== occasion) : [...prev, occasion]))
  }

  function validate(): FormErrors {
    const next: FormErrors = {}
    if (!name.trim()) next.name = 'Garment name is required.'
    if (!category) next.category = 'Select a category.'
    if (!color) next.color = 'Select a primary color.'
    if (!style) next.style = 'Select a style.'
    return next
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const nextErrors = validate()
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0) return

    setSubmitError(null)
    setSaving(true)
    try {
      // Only uploaded (and included below) when the user actually picked a
      // new photo — otherwise `image` is left out of the update entirely,
      // so the backend leaves the item's existing photo field untouched.
      // If this upload or the PUT below fails, nothing has been written to
      // this item's record yet, so its current photo is never at risk.
      const newImageUrl = newImageFile ? await uploadClothingImage(newImageFile) : null

      const updated = await updateWardrobeItem(item.id, {
        name: name.trim(),
        category,
        color,
        style,
        occasion: occasions.length > 0 ? occasions.join(', ') : null,
        season,
        description: description.trim() ? description.trim() : null,
        ...(newImageUrl ? { image: newImageUrl } : {}),
      })
      onSaved(updated)
    } catch (err) {
      setSubmitError(
        err instanceof ApiError
          ? err.message
          : 'Unable to save changes. Make sure the VISTIQ backend is running.',
      )
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title="Edit Item" onClose={saving ? () => {} : onClose} maxWidthClassName="max-w-xl">
      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-5">
        {replacingPhoto ? (
          <div className="flex flex-col gap-2">
            <UploadDropzone file={newImageFile} onFileChange={setNewImageFile} />
            <button
              type="button"
              onClick={() => {
                setReplacingPhoto(false)
                setNewImageFile(null)
              }}
              disabled={saving}
              className="self-start font-label text-label-sm text-secondary transition-colors hover:text-primary disabled:cursor-not-allowed disabled:opacity-60"
            >
              Keep current photo instead
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-4">
            <div className="h-20 w-16 shrink-0 overflow-hidden rounded-lg bg-canvas">
              <GarmentImage src={item.image} alt={item.name} category={item.category} className="h-full w-full object-cover" />
            </div>
            <div className="flex flex-col gap-1.5">
              <p className="font-body text-body-sm text-secondary">Current photo.</p>
              <button
                type="button"
                onClick={() => setReplacingPhoto(true)}
                disabled={saving}
                className="self-start rounded-full bg-canvas px-3.5 py-1.5 font-label text-label-sm text-primary transition-colors hover:bg-border disabled:cursor-not-allowed disabled:opacity-60"
              >
                Change Photo
              </button>
            </div>
          </div>
        )}

        {submitError && (
          <div role="alert" className="flex items-start gap-2.5 rounded-lg bg-red-50 p-3">
            <AlertTriangle size={16} className="mt-0.5 shrink-0 text-red-600" aria-hidden="true" />
            <p className="font-body text-body-sm text-red-700">{submitError}</p>
          </div>
        )}

        <div className="flex flex-col gap-1.5">
          <label htmlFor="edit-name" className="font-label text-label text-primary">
            Garment Name
          </label>
          <input
            id="edit-name"
            type="text"
            value={name}
            onChange={(event) => setName(event.target.value)}
            aria-invalid={Boolean(errors.name)}
            className="h-11 rounded-lg bg-canvas px-4 font-body text-body text-primary focus:bg-surface focus:shadow-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
          />
          {errors.name && (
            <p role="alert" className="font-body text-body-sm text-red-600">
              {errors.name}
            </p>
          )}
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="edit-category" className="font-label text-label text-primary">
            Category
          </label>
          <select
            id="edit-category"
            value={category}
            onChange={(event) => setCategory(event.target.value)}
            aria-invalid={Boolean(errors.category)}
            className="h-11 cursor-pointer rounded-lg bg-canvas px-4 font-body text-body text-primary focus:bg-surface focus:shadow-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
          >
            {CATEGORY_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
          {errors.category && (
            <p role="alert" className="font-body text-body-sm text-red-600">
              {errors.category}
            </p>
          )}
        </div>

        <fieldset className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <legend className="font-label text-label text-primary">Primary Color</legend>
            <span className="font-label-sm text-label-sm font-medium text-secondary">{color || 'None selected'}</span>
          </div>
          <div className="flex flex-wrap items-center gap-3 py-1">
            {COLOR_OPTIONS.map(({ name: colorName, swatch }) => {
              const active = color === colorName
              return (
                <button
                  key={colorName}
                  type="button"
                  onClick={() => setColor(colorName)}
                  aria-pressed={active}
                  aria-label={`Select ${colorName}`}
                  style={{ backgroundColor: swatch }}
                  className={`flex h-8 w-8 items-center justify-center rounded-full border border-border transition-transform hover:scale-110 ${
                    active ? 'scale-110 shadow-md ring-2 ring-primary ring-offset-2' : ''
                  }`}
                >
                  {active && (
                    <Check size={14} strokeWidth={3} className={LIGHT_COLOR_NAMES.has(colorName) ? 'text-primary' : 'text-white'} aria-hidden="true" />
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
          <legend className="font-label text-label text-primary">Style</legend>
          <div className="flex flex-wrap gap-1.5">
            {STYLE_OPTIONS.map((option) => {
              const active = style === option
              return (
                <button
                  key={option}
                  type="button"
                  onClick={() => setStyle(option)}
                  aria-pressed={active}
                  className={`flex items-center gap-1 rounded-full px-3.5 py-1.5 font-label text-label-sm transition-colors ${
                    active ? 'bg-primary text-on-primary shadow-sm' : 'bg-canvas text-secondary hover:text-primary'
                  }`}
                >
                  {option}
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

        <div className="flex flex-col gap-1.5">
          <label htmlFor="edit-description" className="font-label text-label text-primary">
            Description <span className="font-body text-body-sm font-normal text-secondary">(optional)</span>
          </label>
          <input
            id="edit-description"
            type="text"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="e.g. Straight-Leg Selvedge"
            className="h-11 rounded-lg bg-canvas px-4 font-body text-body text-primary placeholder:text-secondary focus:bg-surface focus:shadow-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
          />
        </div>

        <div className="flex justify-end gap-2 pt-1">
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="rounded-full bg-canvas px-5 py-2.5 font-label text-label-sm text-primary transition-colors hover:bg-border disabled:cursor-not-allowed disabled:opacity-60"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={saving}
            className="flex items-center gap-1.5 rounded-full bg-primary px-5 py-2.5 font-label text-label-sm text-on-primary transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {saving && <Loader2 size={14} className="animate-spin" aria-hidden="true" />}
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
