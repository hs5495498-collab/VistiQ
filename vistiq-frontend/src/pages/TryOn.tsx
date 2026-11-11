import { useCallback, useEffect, useRef, useState } from 'react'
import { AlertTriangle, Loader2, RefreshCw, Shirt, Sparkles, Trash2 } from 'lucide-react'
import GarmentImage from '../components/GarmentImage'
import UploadDropzone from '../components/UploadDropzone'
import { useObjectUrl } from '../hooks/useObjectUrl'
import { useWardrobe } from '../hooks/useWardrobe'
import { ApiError, createTryOnJob, deleteTryOnJob, getTryOnJob, listTryOnJobs } from '../services/api'
import type { ClothingItem, TryOnJob } from '../types/clothing'

/** Virtual try-on only makes sense for garments CatVTON can actually place
 * on a body — not Footwear/Accessories. Maps a wardrobe category to the
 * cloth_type the backend (and CatVTON) expects; see docs/virtual-tryon.md. */
const CATEGORY_TO_CLOTH_TYPE: Record<string, 'upper' | 'lower' | 'overall'> = {
  Tops: 'upper',
  Outerwear: 'upper',
  Bottoms: 'lower',
  Dresses: 'overall',
}

const POLL_INTERVAL_MS = 2000

function isUnavailable(job: TryOnJob): boolean {
  return job.status === 'failed' && (job.errorMessage?.toLowerCase().includes('unavailable') ?? false)
}

export default function TryOn() {
  const { items: wardrobeItems, loading: wardrobeLoading } = useWardrobe()
  const eligibleItems = wardrobeItems.filter((item) => item.image && CATEGORY_TO_CLOTH_TYPE[item.category])

  const [selectedGarment, setSelectedGarment] = useState<ClothingItem | null>(null)
  const [personImage, setPersonImage] = useState<File | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [activeJob, setActiveJob] = useState<TryOnJob | null>(null)

  const personImagePreviewUrl = useObjectUrl(personImage)

  const [history, setHistory] = useState<TryOnJob[]>([])
  const [historyLoading, setHistoryLoading] = useState(true)
  const [historyError, setHistoryError] = useState<string | null>(null)
  const [historyReloadToken, setHistoryReloadToken] = useState(0)

  // Same "adjust state during render" pattern as useWardrobe.ts's
  // reloadToken: resetting to a fresh loading state happens here (during
  // render), not as a direct setState call in the effect body below, which
  // triggers a lint error (react-hooks/set-state-in-effect) for causing an
  // extra cascading render.
  const [lastHandledHistoryToken, setLastHandledHistoryToken] = useState(historyReloadToken)
  if (lastHandledHistoryToken !== historyReloadToken) {
    setLastHandledHistoryToken(historyReloadToken)
    setHistoryLoading(true)
    setHistoryError(null)
  }

  const loadHistory = useCallback(() => setHistoryReloadToken((token) => token + 1), [])

  useEffect(() => {
    let cancelled = false
    listTryOnJobs()
      .then((jobs) => {
        if (!cancelled) setHistory(jobs)
      })
      .catch((err: unknown) => {
        if (!cancelled) setHistoryError(err instanceof ApiError ? err.message : 'Unable to load your try-on history.')
      })
      .finally(() => {
        if (!cancelled) setHistoryLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [historyReloadToken])

  // Poll the active job until it reaches a terminal status. A ref (not
  // state) tracks the interval id so the cleanup function always clears
  // the one actually running, even across re-renders triggered by the
  // poll itself updating activeJob.
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!activeJob || activeJob.status === 'completed' || activeJob.status === 'failed') {
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
      return
    }

    pollRef.current = setInterval(() => {
      getTryOnJob(activeJob.id)
        .then((updated) => {
          setActiveJob(updated)
          if (updated.status === 'completed' || updated.status === 'failed') {
            loadHistory()
          }
        })
        .catch(() => {
          // A transient poll failure shouldn't end the attempt — the next
          // tick tries again. The job itself is unaffected server-side.
        })
    }, POLL_INTERVAL_MS)

    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeJob?.id, activeJob?.status])

  async function handleSubmit() {
    if (!selectedGarment) {
      setSubmitError('Select a wardrobe garment to try on.')
      return
    }
    if (!personImage) {
      setSubmitError('Upload a photo of yourself to try the garment on.')
      return
    }
    const clothType = CATEGORY_TO_CLOTH_TYPE[selectedGarment.category]
    if (!clothType) {
      setSubmitError('This garment type is not supported for virtual try-on yet.')
      return
    }

    setSubmitError(null)
    setSubmitting(true)
    try {
      const job = await createTryOnJob({ garmentItemId: selectedGarment.id, clothType, personImage })
      setActiveJob(job)
      loadHistory()
    } catch (err) {
      setSubmitError(
        err instanceof ApiError ? err.message : 'Unable to start virtual try-on. Make sure the VISTIQ backend is running.',
      )
    } finally {
      setSubmitting(false)
    }
  }

  async function handleDelete(id: TryOnJob['id']) {
    try {
      await deleteTryOnJob(id)
      setHistory((prev) => prev.filter((job) => job.id !== id))
      setActiveJob((prev) => (prev?.id === id ? null : prev))
    } catch {
      // Best-effort — the row stays visible and the user can try again.
    }
  }

  const isPolling = activeJob && (activeJob.status === 'pending' || activeJob.status === 'processing')

  return (
    <section className="mx-auto max-w-6xl px-6 py-10">
      <div className="mb-6 max-w-xl">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-canvas px-3 py-1 font-label-sm text-label-sm uppercase tracking-wider text-secondary">
          <Sparkles size={14} aria-hidden="true" />
          Experimental
        </span>
        <h1 className="mt-2 font-heading text-h1 text-primary">Virtual Try-On</h1>
        <p className="mt-1 font-body text-body text-secondary">
          See one of your own wardrobe garments on a photo of yourself, generated by a research model (CatVTON).
          This feature depends on a separately-running GPU worker — see the note below if it's unavailable.
        </p>
      </div>

      <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-12">
        <section className="flex flex-col gap-6 rounded-2xl bg-surface p-4 shadow-sm md:p-6 lg:col-span-7">
          <fieldset className="flex flex-col gap-2">
            <legend className="font-label-sm text-label-sm font-semibold uppercase tracking-wider text-secondary">
              01. Choose a garment from your wardrobe
            </legend>
            {wardrobeLoading ? (
              <p className="py-4 font-body text-body-sm text-secondary">Loading your wardrobe...</p>
            ) : eligibleItems.length === 0 ? (
              <p className="py-4 font-body text-body-sm text-secondary">
                None of your wardrobe items support virtual try-on yet — add a Top, Bottom, Outerwear piece, or
                Dress with a photo first.
              </p>
            ) : (
              <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
                {eligibleItems.map((item) => {
                  const active = selectedGarment?.id === item.id
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => setSelectedGarment(item)}
                      aria-pressed={active}
                      className={`flex flex-col items-center gap-1 rounded-xl p-2 text-center transition-colors ${
                        active ? 'bg-primary text-on-primary shadow-sm' : 'bg-canvas hover:bg-border'
                      }`}
                    >
                      <span className="block h-16 w-16 overflow-hidden rounded-lg bg-surface">
                        <GarmentImage src={item.image} alt={item.name} category={item.category} className="h-full w-full object-cover" />
                      </span>
                      <span className={`block w-full truncate font-label-sm text-label-sm font-semibold ${active ? '' : 'text-primary'}`}>
                        {item.name}
                      </span>
                    </button>
                  )
                })}
              </div>
            )}
          </fieldset>

          <fieldset className="flex flex-col gap-2">
            <legend className="font-label-sm text-label-sm font-semibold uppercase tracking-wider text-secondary">
              02. Upload a photo of yourself
            </legend>
            <p className="font-body text-body-sm text-secondary">
              A clear, full-body, front-facing photo works best. Only you can see this photo and the result.
            </p>
            <UploadDropzone file={personImage} onFileChange={setPersonImage} label="Your photo" fieldId="tryon-person-photo" />
          </fieldset>

          <div className="flex flex-col items-center gap-2 pt-1">
            <button
              type="button"
              onClick={handleSubmit}
              disabled={submitting || Boolean(isPolling)}
              className="flex w-full items-center justify-center gap-2 rounded-full bg-primary px-6 py-3.5 font-label text-label font-semibold tracking-wide text-on-primary shadow-md transition-all hover:opacity-90 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {submitting || isPolling ? (
                <>
                  <Loader2 size={20} className="animate-spin" aria-hidden="true" />
                  {submitting ? 'Starting try-on...' : 'Generating your look...'}
                </>
              ) : (
                <>
                  <Shirt size={20} aria-hidden="true" />
                  Generate Virtual Try-On
                </>
              )}
            </button>
            {submitError && (
              <p role="alert" className="flex items-center gap-1.5 font-body text-body-sm text-red-600">
                <AlertTriangle size={14} aria-hidden="true" />
                {submitError}
              </p>
            )}
          </div>
        </section>

        <aside className="flex flex-col gap-4 lg:col-span-5">
          <div className="flex flex-col gap-3 rounded-2xl bg-surface p-4 shadow-sm md:p-5">
            <h2 className="font-heading text-h3 font-semibold text-primary">Result</h2>

            {!activeJob && (
              <p className="py-6 text-center font-body text-body-sm text-secondary">
                Choose a garment and a photo, then generate your try-on.
              </p>
            )}

            {activeJob && isPolling && (
              <div className="flex flex-col items-center gap-2 py-8 text-center">
                <Loader2 size={28} className="animate-spin text-secondary" aria-hidden="true" />
                <p className="font-body text-body-sm text-secondary">
                  Generating your look — this can take a minute or two on the GPU worker.
                </p>
              </div>
            )}

            {activeJob && activeJob.status === 'failed' && (
              <div className="flex flex-col items-center gap-2 py-8 text-center">
                <AlertTriangle size={24} className="text-red-500" aria-hidden="true" />
                <p className="font-body text-body-sm text-secondary">
                  {isUnavailable(activeJob)
                    ? 'Virtual try-on is currently unavailable — no GPU worker is connected. Infrastructure for this feature is in place, but there is nothing to generate a result right now.'
                    : (activeJob.errorMessage ?? 'This attempt failed.')}
                </p>
                {!isUnavailable(activeJob) && (
                  <button
                    type="button"
                    onClick={handleSubmit}
                    className="mt-1 flex items-center gap-1.5 rounded-full bg-canvas px-4 py-1.5 font-label text-label-sm text-primary transition-colors hover:bg-border"
                  >
                    <RefreshCw size={14} aria-hidden="true" />
                    Try again
                  </button>
                )}
              </div>
            )}

            {activeJob && activeJob.status === 'completed' && activeJob.resultImage && (
              <div className="flex flex-col gap-3">
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <p className="mb-1 font-label-sm text-label-sm uppercase text-secondary">Before</p>
                    <div className="aspect-[3/4] overflow-hidden rounded-xl bg-canvas">
                      {personImagePreviewUrl && (
                        <img src={personImagePreviewUrl} alt="Your uploaded photo" className="h-full w-full object-cover" />
                      )}
                    </div>
                  </div>
                  <div>
                    <p className="mb-1 font-label-sm text-label-sm uppercase text-secondary">After</p>
                    <div className="aspect-[3/4] overflow-hidden rounded-xl bg-canvas">
                      <img src={activeJob.resultImage} alt="Generated virtual try-on result" className="h-full w-full object-cover" />
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="flex flex-col gap-2 rounded-2xl bg-surface p-4 shadow-sm md:p-5">
            <h2 className="font-heading text-h3 font-semibold text-primary">Your try-on history</h2>
            {historyLoading ? (
              <p className="py-2 font-body text-body-sm text-secondary">Loading...</p>
            ) : historyError ? (
              <p className="py-2 font-body text-body-sm text-secondary">{historyError}</p>
            ) : history.length === 0 ? (
              <p className="py-2 font-body text-body-sm text-secondary">No try-on attempts yet.</p>
            ) : (
              <ul className="flex flex-col gap-2">
                {history.map((job) => (
                  <li key={job.id} className="flex items-center gap-2.5 rounded-xl bg-canvas p-2">
                    <span className="block h-10 w-10 shrink-0 overflow-hidden rounded-lg bg-surface">
                      {job.resultImage && <img src={job.resultImage} alt="" className="h-full w-full object-cover" />}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block font-label text-label-sm font-semibold capitalize text-primary">
                        {job.status}
                      </span>
                      <span className="block truncate font-label-sm text-label-sm text-secondary">
                        {new Date(job.createdAt).toLocaleString()}
                      </span>
                    </span>
                    <button
                      type="button"
                      onClick={() => handleDelete(job.id)}
                      aria-label="Delete this try-on attempt"
                      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-secondary transition-colors hover:bg-border hover:text-red-600"
                    >
                      <Trash2 size={14} aria-hidden="true" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </aside>
      </div>
    </section>
  )
}
