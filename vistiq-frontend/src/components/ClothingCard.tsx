import { Heart, Pencil, Trash2 } from 'lucide-react'
import GarmentImage from './GarmentImage'
import type { ClothingItem } from '../types/clothing'

interface ClothingCardProps {
  item: ClothingItem
  isFavorite?: boolean
  onToggleFavorite?: (id: ClothingItem['id']) => void
  isSelected?: boolean
  onSelect?: (id: ClothingItem['id']) => void
  onEdit?: (item: ClothingItem) => void
  onDelete?: (item: ClothingItem) => void
}

export default function ClothingCard({
  item,
  isFavorite = false,
  onToggleFavorite,
  isSelected = false,
  onSelect,
  onEdit,
  onDelete,
}: ClothingCardProps) {
  return (
    <article
      className={`flex flex-col overflow-hidden rounded-xl bg-surface shadow-sm transition-shadow hover:shadow-md ${
        isSelected ? 'ring-2 ring-primary' : ''
      }`}
    >
      <div className="relative aspect-[4/5] w-full overflow-hidden bg-canvas">
        <button
          type="button"
          onClick={() => onSelect?.(item.id)}
          aria-pressed={isSelected}
          aria-label={`${isSelected ? 'Deselect' : 'Select'} ${item.name}`}
          className="group absolute inset-0 z-0"
        >
          <GarmentImage
            src={item.image}
            alt={item.name}
            category={item.category}
            className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
          />
        </button>

        <span className="pointer-events-none absolute left-3 top-3 z-10 rounded-full bg-surface/90 px-2.5 py-1 font-label-sm text-label-sm text-primary shadow-sm backdrop-blur-sm">
          {item.category}
        </span>

        {onToggleFavorite && (
          <button
            type="button"
            onClick={() => onToggleFavorite(item.id)}
            aria-pressed={isFavorite}
            aria-label={isFavorite ? `Remove ${item.name} from favorites` : `Add ${item.name} to favorites`}
            className={`absolute right-3 top-3 z-10 flex h-8 w-8 items-center justify-center rounded-full bg-surface/90 shadow-sm backdrop-blur-sm transition-colors ${
              isFavorite ? 'text-red-500' : 'text-secondary hover:text-primary'
            }`}
          >
            <Heart size={16} strokeWidth={2} className={isFavorite ? 'fill-current' : ''} aria-hidden="true" />
          </button>
        )}
      </div>

      <div className="flex flex-1 flex-col justify-between p-4">
        <div>
          <h3 className="font-heading text-h3 text-primary">{item.name}</h3>
          {item.description && (
            <p className="mt-0.5 font-body text-body-sm text-secondary">{item.description}</p>
          )}
        </div>
        <div className="mt-4 flex items-center justify-between gap-2 pt-3">
          <div className="flex min-w-0 items-center gap-2">
            <span className="rounded-md bg-canvas px-2 py-0.5 font-label-sm text-label-sm text-secondary">
              {item.style}
            </span>
            {typeof item.wearCount === 'number' && (
              <span className="flex shrink-0 items-center gap-1 font-label-sm text-label-sm text-secondary">
                <span className="h-1.5 w-1.5 rounded-full bg-secondary" aria-hidden="true" />
                Worn {item.wearCount}x
              </span>
            )}
          </div>

          {(onEdit || onDelete) && (
            <div className="flex shrink-0 items-center gap-1">
              {onEdit && (
                <button
                  type="button"
                  onClick={() => onEdit(item)}
                  aria-label={`Edit ${item.name}`}
                  title="Edit"
                  className="flex h-7 w-7 items-center justify-center rounded-full text-secondary transition-colors hover:bg-canvas hover:text-primary"
                >
                  <Pencil size={14} strokeWidth={2} aria-hidden="true" />
                </button>
              )}
              {onDelete && (
                <button
                  type="button"
                  onClick={() => onDelete(item)}
                  aria-label={`Delete ${item.name}`}
                  title="Delete"
                  className="flex h-7 w-7 items-center justify-center rounded-full text-secondary transition-colors hover:bg-red-50 hover:text-red-600"
                >
                  <Trash2 size={14} strokeWidth={2} aria-hidden="true" />
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </article>
  )
}
