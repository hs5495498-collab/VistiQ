import { useState } from 'react'
import { Footprints, Layers, Package, Shirt, Watch, type LucideIcon } from 'lucide-react'
import topsIllustration from '../assets/illustrations/category-tops.svg'
import bottomsIllustration from '../assets/illustrations/category-bottoms.svg'
import footwearIllustration from '../assets/illustrations/category-footwear.svg'

const CATEGORY_ILLUSTRATIONS: Record<string, string> = {
  Tops: topsIllustration,
  Bottoms: bottomsIllustration,
  Footwear: footwearIllustration,
}

const CATEGORY_ICONS: Record<string, LucideIcon> = {
  Tops: Shirt,
  Dresses: Shirt,
  Bottoms: Package,
  Outerwear: Layers,
  Footwear: Footprints,
  Accessories: Watch,
}

interface GarmentImageProps {
  /** The real uploaded wardrobe photo URL, if any. */
  src?: string | null
  /** Meaningful alt text used only when a real photo is shown. */
  alt: string
  category: string
  /** Applied to whichever visual actually renders (real photo or
   * illustration) so both get identical sizing/hover treatment. */
  className?: string
}

/**
 * Single source of truth for how a garment photo is displayed anywhere in
 * VISTIQ (My Wardrobe cards, recommendation outfit cards, AI Stylist pool).
 *
 * Priority: real uploaded image > a tasteful local illustration for the
 * three categories we have one for > a plain category icon. A real image
 * that fails to load (broken URL, deleted file) falls back the same way —
 * never a broken-image glyph. This never invents a photo for an item that
 * doesn't have one.
 */
export default function GarmentImage({ src, alt, category, className }: GarmentImageProps) {
  const [broken, setBroken] = useState(false)
  const imgClassName = className ?? 'h-full w-full object-cover'

  if (src && !broken) {
    return <img src={src} alt={alt} loading="lazy" onError={() => setBroken(true)} className={imgClassName} />
  }

  const illustration = CATEGORY_ILLUSTRATIONS[category]
  if (illustration) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-canvas">
        {/* Decorative stand-in for a missing photo — the category badge
         * elsewhere on the card already conveys this information, so it's
         * hidden from assistive tech rather than duplicated as alt text. */}
        <img src={illustration} alt="" aria-hidden="true" loading="lazy" className={imgClassName} />
      </div>
    )
  }

  const Icon = CATEGORY_ICONS[category] ?? Shirt
  return (
    <div className="flex h-full w-full items-center justify-center bg-canvas">
      <Icon size={36} strokeWidth={1.5} className="text-secondary" aria-hidden="true" />
    </div>
  )
}
