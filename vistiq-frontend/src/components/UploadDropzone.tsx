import { useRef, useState } from 'react'
import { ImagePlus, Upload, X } from 'lucide-react'
import { useObjectUrl } from '../hooks/useObjectUrl'
import garmentIllustration from '../assets/illustrations/category-tops.svg'

const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/webp']
const DEFAULT_MAX_SIZE_MB = 10

interface UploadDropzoneProps {
  file: File | null
  onFileChange: (file: File | null) => void
  error?: string
  maxSizeMB?: number
}

export default function UploadDropzone({ file, onFileChange, error, maxSizeMB = DEFAULT_MAX_SIZE_MB }: UploadDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)
  const previewUrl = useObjectUrl(file)
  const displayError = error ?? localError ?? undefined

  function handleFiles(fileList: FileList | null) {
    const selected = fileList?.[0]
    if (!selected) return
    if (!ACCEPTED_TYPES.includes(selected.type)) {
      setLocalError('Please upload a JPG, PNG, or WEBP image.')
      return
    }
    if (selected.size > maxSizeMB * 1024 * 1024) {
      setLocalError(`Image must be smaller than ${maxSizeMB}MB.`)
      return
    }
    setLocalError(null)
    onFileChange(selected)
  }

  function handleRemove() {
    setLocalError(null)
    onFileChange(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  const fileInput = (
    <input
      ref={inputRef}
      id="garment-photo"
      type="file"
      accept={ACCEPTED_TYPES.join(',')}
      className="hidden"
      onChange={(event) => handleFiles(event.target.files)}
    />
  )

  if (file && previewUrl) {
    return (
      <div className="flex flex-col gap-3">
        <div className="relative aspect-[4/5] w-full overflow-hidden rounded-xl bg-canvas shadow-sm">
          <img src={previewUrl} alt="Selected garment preview" className="h-full w-full object-cover" />
          <button
            type="button"
            onClick={handleRemove}
            aria-label="Remove selected photo"
            className="absolute right-3 top-3 flex h-8 w-8 items-center justify-center rounded-full bg-surface/90 text-secondary shadow-sm backdrop-blur-sm transition-colors hover:text-primary"
          >
            <X size={16} aria-hidden="true" />
          </button>
        </div>
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="self-start rounded-full bg-surface px-4 py-2 font-label text-label-sm text-primary shadow-sm transition-colors hover:bg-canvas"
        >
          Change photo
        </button>
        {fileInput}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor="garment-photo" className="sr-only">
        Garment photo
      </label>
      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={(event) => {
          event.preventDefault()
          setIsDragging(true)
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(event) => {
          event.preventDefault()
          setIsDragging(false)
          handleFiles(event.dataTransfer.files)
        }}
        className={`relative flex aspect-[4/5] w-full cursor-pointer flex-col items-center justify-center gap-2 overflow-hidden rounded-xl border border-dashed p-8 text-center transition-colors ${
          isDragging ? 'border-primary bg-canvas' : 'border-border bg-canvas/60 hover:bg-canvas'
        }`}
      >
        {/* Faint editorial backdrop reinforcing "this becomes a fashion
         * photo" — purely decorative, hidden from assistive tech. */}
        <img
          src={garmentIllustration}
          alt=""
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 h-full w-full object-cover opacity-[0.07]"
        />

        <span className="relative flex h-14 w-14 items-center justify-center rounded-full bg-surface text-primary shadow-sm" aria-hidden="true">
          <Upload size={24} />
        </span>
        <p className="relative font-heading text-h3 text-primary">Drag &amp; drop your garment photo</p>
        <p className="relative font-body text-body-sm text-secondary">Supports JPG, PNG, WEBP up to {maxSizeMB}MB</p>
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation()
            inputRef.current?.click()
          }}
          className="relative mt-1 inline-flex items-center gap-1.5 rounded-full bg-surface px-4 py-2 font-label text-label-sm text-primary shadow-sm transition-colors hover:bg-canvas"
        >
          <ImagePlus size={16} aria-hidden="true" />
          Choose file from device
        </button>
        {fileInput}
      </div>
      {displayError && (
        <p role="alert" className="font-body text-body-sm text-red-600">
          {displayError}
        </p>
      )}
    </div>
  )
}
