import { useEffect, useMemo } from 'react'

/** Creates a browser object URL for a File and revokes it when the file changes or unmounts. */
export function useObjectUrl(file: File | null): string | null {
  const url = useMemo(() => (file ? URL.createObjectURL(file) : null), [file])

  useEffect(() => {
    return () => {
      if (url) URL.revokeObjectURL(url)
    }
  }, [url])

  return url
}
