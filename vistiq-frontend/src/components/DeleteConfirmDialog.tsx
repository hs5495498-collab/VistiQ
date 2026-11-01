import { useState } from 'react'
import { AlertTriangle, Loader2 } from 'lucide-react'
import Modal from './Modal'
import { ApiError, deleteWardrobeItem } from '../services/api'
import type { ClothingItem } from '../types/clothing'

interface DeleteConfirmDialogProps {
  item: ClothingItem
  onClose: () => void
  /** Called only after DELETE /wardrobe/{id} actually succeeded. */
  onDeleted: (id: ClothingItem['id']) => void
}

export default function DeleteConfirmDialog({ item, onClose, onDeleted }: DeleteConfirmDialogProps) {
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleConfirm() {
    setDeleting(true)
    setError(null)
    try {
      await deleteWardrobeItem(item.id)
      onDeleted(item.id)
    } catch (err) {
      // Keep the item visible and tell the user exactly what happened —
      // never pretend the deletion succeeded when the API call failed.
      setError(
        err instanceof ApiError
          ? err.message
          : 'Unable to delete this item. Make sure the VISTIQ backend is running.',
      )
      setDeleting(false)
    }
  }

  return (
    <Modal title="Delete this wardrobe item?" onClose={deleting ? () => {} : onClose} maxWidthClassName="max-w-md">
      <div className="flex flex-col gap-4">
        <div className="flex items-start gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-red-50 text-red-600">
            <AlertTriangle size={20} aria-hidden="true" />
          </span>
          <p className="font-body text-body text-secondary">
            Are you sure you want to remove <span className="font-medium text-primary">&ldquo;{item.name}&rdquo;</span>{' '}
            from your wardrobe? This action cannot be undone.
          </p>
        </div>

        {error && (
          <div role="alert" className="rounded-lg bg-red-50 p-3 font-body text-body-sm text-red-700">
            {error}
          </div>
        )}

        <div className="flex justify-end gap-2 pt-1">
          <button
            type="button"
            onClick={onClose}
            disabled={deleting}
            className="rounded-full bg-canvas px-5 py-2.5 font-label text-label-sm text-primary transition-colors hover:bg-border disabled:cursor-not-allowed disabled:opacity-60"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={deleting}
            className="flex items-center gap-1.5 rounded-full bg-red-600 px-5 py-2.5 font-label text-label-sm text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {deleting && <Loader2 size={14} className="animate-spin" aria-hidden="true" />}
            {deleting ? 'Deleting...' : 'Delete'}
          </button>
        </div>
      </div>
    </Modal>
  )
}
