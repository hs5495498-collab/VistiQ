import { useCallback, useEffect, useState } from 'react'
import { ApiError, getWardrobe } from '../services/api'
import type { ClothingItem } from '../types/clothing'

interface UseWardrobeResult {
  items: ClothingItem[]
  loading: boolean
  error: string | null
  refetch: () => void
  /** Splices a server-confirmed updated record into the already-loaded
   * list — call only with what a successful PUT /wardrobe/{id} actually
   * returned, never a locally-guessed value. Avoids a full refetch (and
   * the loading-state flash that comes with it) for a single-item edit. */
  applyUpdatedItem: (item: ClothingItem) => void
  /** Removes one item from the already-loaded list — call only after a
   * confirmed DELETE /wardrobe/{id} (200) response. */
  removeItem: (id: ClothingItem['id']) => void
}

/** Fetches the real wardrobe from the backend. Shared by Wardrobe and
 * AI Stylist so both pages use the exact same live data and loading/error
 * handling instead of duplicating fetch logic. */
export function useWardrobe(): UseWardrobeResult {
  const [items, setItems] = useState<ClothingItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [reloadToken, setReloadToken] = useState(0)

  // Whenever a reload is triggered, reset to a fresh loading state during
  // render (React's "adjust state during render" pattern) rather than
  // calling setState synchronously inside the effect below.
  const [lastHandledToken, setLastHandledToken] = useState(reloadToken)
  if (lastHandledToken !== reloadToken) {
    setLastHandledToken(reloadToken)
    setLoading(true)
    setError(null)
  }

  useEffect(() => {
    let cancelled = false

    getWardrobe()
      .then((fetched) => {
        if (cancelled) return
        setItems(fetched)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setError(
          err instanceof ApiError
            ? err.message
            : 'Unable to load your wardrobe. Make sure the VISTIQ backend is running.',
        )
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [reloadToken])

  const refetch = useCallback(() => setReloadToken((token) => token + 1), [])

  const applyUpdatedItem = useCallback((updated: ClothingItem) => {
    setItems((prev) => prev.map((item) => (item.id === updated.id ? updated : item)))
  }, [])

  const removeItem = useCallback((id: ClothingItem['id']) => {
    setItems((prev) => prev.filter((item) => item.id !== id))
  }, [])

  return { items, loading, error, refetch, applyUpdatedItem, removeItem }
}
