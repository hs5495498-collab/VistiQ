import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertTriangle,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Plus,
  RefreshCw,
  Search,
  Shirt,
  SlidersHorizontal,
  X,
} from 'lucide-react'
import ClothingCard from '../components/ClothingCard'
import DeleteConfirmDialog from '../components/DeleteConfirmDialog'
import EditItemModal from '../components/EditItemModal'
import FilterSidebar, { type CategoryOption, type ColorOption } from '../components/FilterSidebar'
import { useWardrobe } from '../hooks/useWardrobe'
import { updateWardrobeItem } from '../services/api'
import type { ClothingItem } from '../types/clothing'

type SortOption = 'Recently Added' | 'Most Worn' | 'Least Worn' | 'Name (A-Z)'

const ALL_CATEGORIES = 'All Items'
const CATEGORY_ORDER = ['Tops', 'Bottoms', 'Outerwear', 'Footwear', 'Accessories']
const STYLE_ORDER = ['Casual', 'Smart Casual', 'Minimal', 'Formal', 'Streetwear', 'Sporty']
const SEASON_OPTIONS = ['All Season', 'Warm Weather', 'Cool Weather', 'Layering Pieces']
const SORT_OPTIONS: SortOption[] = ['Recently Added', 'Most Worn', 'Least Worn', 'Name (A-Z)']
const COLOR_SWATCHES: Record<string, string> = {
  Black: '#18181b',
  White: '#f4f4f5',
  Navy: '#243b55',
  Indigo: '#3c4a75',
  Beige: '#d9cdb8',
  Grey: '#9ca3af',
}
const PAGE_SIZE = 6

function matchesSearch(item: ClothingItem, query: string) {
  if (!query) return true
  const haystack = [item.name, item.category, item.color, item.style, item.description]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
  return haystack.includes(query.toLowerCase())
}

export default function Wardrobe() {
  const { items, loading, error, refetch, applyUpdatedItem, removeItem } = useWardrobe()

  const [editingItem, setEditingItem] = useState<ClothingItem | null>(null)
  const [deletingItem, setDeletingItem] = useState<ClothingItem | null>(null)

  const [search, setSearch] = useState('')
  const [category, setCategory] = useState(ALL_CATEGORIES)
  const [activeStyles, setActiveStyles] = useState<string[]>([])
  const [activeColors, setActiveColors] = useState<string[]>([])
  const [season, setSeason] = useState('All Season')
  const [sort, setSort] = useState<SortOption>('Recently Added')
  const [selectedId, setSelectedId] = useState<ClothingItem['id'] | null>(null)
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [page, setPage] = useState(1)

  const categories: CategoryOption[] = useMemo(() => {
    const options: CategoryOption[] = [{ label: ALL_CATEGORIES, count: items.length }]
    for (const cat of CATEGORY_ORDER) {
      const count = items.filter((item) => item.category === cat).length
      if (count > 0) options.push({ label: cat, count })
    }
    return options
  }, [items])

  const styleOptions = useMemo(
    () => STYLE_ORDER.filter((style) => items.some((item) => item.style === style)),
    [items],
  )

  const colors: ColorOption[] = useMemo(() => {
    const counts = new Map<string, number>()
    for (const item of items) counts.set(item.color, (counts.get(item.color) ?? 0) + 1)
    return Array.from(counts.entries()).map(([name, count]) => ({
      name,
      count,
      swatch: COLOR_SWATCHES[name] ?? '#a1a1aa',
    }))
  }, [items])

  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      const categoryMatch = category === ALL_CATEGORIES || item.category === category
      const styleMatch = activeStyles.length === 0 || activeStyles.includes(item.style)
      const colorMatch = activeColors.length === 0 || activeColors.includes(item.color)
      const seasonMatch = season === 'All Season' || (item.season ?? []).includes(season)
      return categoryMatch && styleMatch && colorMatch && seasonMatch && matchesSearch(item, search)
    })
  }, [items, category, activeStyles, activeColors, season, search])

  const sortedItems = useMemo(() => {
    const items = [...filteredItems]
    switch (sort) {
      case 'Most Worn':
        return items.sort((a, b) => (b.wearCount ?? 0) - (a.wearCount ?? 0))
      case 'Least Worn':
        return items.sort((a, b) => (a.wearCount ?? 0) - (b.wearCount ?? 0))
      case 'Name (A-Z)':
        return items.sort((a, b) => a.name.localeCompare(b.name))
      case 'Recently Added':
      default:
        return items.sort((a, b) => (b.addedAt ?? '').localeCompare(a.addedAt ?? ''))
    }
  }, [filteredItems, sort])

  const totalPages = Math.max(1, Math.ceil(sortedItems.length / PAGE_SIZE))

  // Reset to page 1 whenever the filter/sort criteria change, following React's
  // "adjust state during render" pattern instead of an effect (avoids an extra render).
  const filterSignature = JSON.stringify([category, activeStyles, activeColors, season, search, sort])
  const [previousSignature, setPreviousSignature] = useState(filterSignature)
  if (filterSignature !== previousSignature) {
    setPreviousSignature(filterSignature)
    setPage(1)
  }

  const currentPage = Math.min(page, totalPages)
  const paginatedItems = sortedItems.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE)

  function toggleStyle(style: string) {
    setActiveStyles((prev) => (prev.includes(style) ? prev.filter((s) => s !== style) : [...prev, style]))
  }

  function toggleColor(color: string) {
    setActiveColors((prev) => (prev.includes(color) ? prev.filter((c) => c !== color) : [...prev, color]))
  }

  async function toggleFavorite(id: ClothingItem['id']) {
    const item = items.find((candidate) => candidate.id === id)
    if (!item) return
    try {
      const updated = await updateWardrobeItem(id, { isFavorite: !item.isFavorite })
      applyUpdatedItem(updated)
    } catch {
      // Best-effort — a failed favorite toggle isn't critical enough to
      // interrupt browsing, and the UI already reflects the last confirmed
      // server state (no optimistic update was applied).
    }
  }

  function handleDeleted(id: ClothingItem['id']) {
    removeItem(id)
    setSelectedId((current) => (current === id ? null : current))
    setDeletingItem(null)
  }

  function resetFilters() {
    setCategory(ALL_CATEGORIES)
    setActiveStyles([])
    setActiveColors([])
    setSeason('All Season')
  }

  function clearAll() {
    resetFilters()
    setSearch('')
    setSort('Recently Added')
  }

  const activeChips = [
    ...(category !== ALL_CATEGORIES ? [{ key: `cat-${category}`, label: category, onRemove: () => setCategory(ALL_CATEGORIES) }] : []),
    ...activeStyles.map((style) => ({ key: `style-${style}`, label: style, onRemove: () => toggleStyle(style) })),
    ...activeColors.map((color) => ({ key: `color-${color}`, label: color, onRemove: () => toggleColor(color) })),
    ...(season !== 'All Season' ? [{ key: `season-${season}`, label: season, onRemove: () => setSeason('All Season') }] : []),
    ...(search ? [{ key: 'search', label: `"${search}"`, onRemove: () => setSearch('') }] : []),
  ]

  if (loading) {
    return (
      <section className="mx-auto max-w-7xl px-6 py-10">
        <h1 className="font-heading text-h1 text-primary">My Wardrobe</h1>
        <div className="mt-8 flex items-center justify-center rounded-xl bg-surface p-16 shadow-sm">
          <p className="font-body text-body text-secondary">Loading wardrobe...</p>
        </div>
      </section>
    )
  }

  if (error) {
    return (
      <section className="mx-auto max-w-7xl px-6 py-10">
        <h1 className="font-heading text-h1 text-primary">My Wardrobe</h1>
        <div className="mt-8 flex flex-col items-center gap-3 rounded-xl bg-surface p-16 text-center shadow-sm">
          <AlertTriangle size={28} className="text-red-500" aria-hidden="true" />
          <p className="font-heading text-h3 text-primary">Unable to load your wardrobe</p>
          <p className="max-w-md font-body text-body-sm text-secondary">{error}</p>
          <button
            type="button"
            onClick={refetch}
            className="mt-2 flex items-center gap-1.5 rounded-full bg-primary px-5 py-2 font-label text-label-sm text-on-primary transition-opacity hover:opacity-90"
          >
            <RefreshCw size={14} aria-hidden="true" />
            Try again
          </button>
        </div>
      </section>
    )
  }

  if (items.length === 0) {
    return (
      <section className="mx-auto max-w-7xl px-6 py-10">
        <h1 className="font-heading text-h1 text-primary">My Wardrobe</h1>
        <div className="mt-8 flex flex-col items-center gap-3 rounded-xl bg-surface p-16 text-center shadow-sm">
          <span className="flex h-14 w-14 items-center justify-center rounded-full bg-canvas text-primary">
            <Shirt size={26} aria-hidden="true" />
          </span>
          <p className="font-heading text-h3 text-primary">Your wardrobe is empty</p>
          <p className="max-w-md font-body text-body-sm text-secondary">
            Add your first garment to start building outfit recommendations.
          </p>
          <Link
            to="/add-item"
            className="mt-2 flex items-center gap-1.5 rounded-full bg-primary px-5 py-2 font-label text-label-sm text-on-primary transition-opacity hover:opacity-90"
          >
            <Plus size={16} aria-hidden="true" />
            Add Item
          </Link>
        </div>
      </section>
    )
  }

  return (
    <section className="mx-auto max-w-7xl px-6 py-10">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="font-heading text-h1 text-primary">My Wardrobe</h1>
          <p className="mt-1 font-body text-body text-secondary">
            {items.length} garments in your personal collection
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="relative flex items-center">
            <Search size={18} className="pointer-events-none absolute left-3 text-secondary" aria-hidden="true" />
            <label htmlFor="wardrobe-search" className="sr-only">
              Search your wardrobe
            </label>
            <input
              id="wardrobe-search"
              type="text"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search by name, category, color..."
              className="h-10 w-56 rounded-full bg-surface pl-9 pr-4 font-body text-body-sm text-primary shadow-sm placeholder:text-secondary focus:outline-none focus:ring-2 focus:ring-primary/20 sm:w-64"
            />
          </div>

          <div className="relative">
            <label htmlFor="wardrobe-sort" className="sr-only">
              Sort wardrobe
            </label>
            <select
              id="wardrobe-sort"
              value={sort}
              onChange={(event) => setSort(event.target.value as SortOption)}
              className="h-10 cursor-pointer appearance-none rounded-full bg-surface py-2 pl-4 pr-9 font-label text-label-sm text-primary shadow-sm focus:outline-none"
            >
              {SORT_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  Sort by: {option}
                </option>
              ))}
            </select>
            <ChevronDown size={16} className="pointer-events-none absolute right-3 top-3 text-secondary" aria-hidden="true" />
          </div>

          <button
            type="button"
            onClick={() => setFiltersOpen((open) => !open)}
            aria-pressed={filtersOpen}
            className="flex h-10 items-center gap-1.5 rounded-full bg-surface px-4 font-label text-label-sm text-primary shadow-sm lg:hidden"
          >
            <SlidersHorizontal size={16} aria-hidden="true" />
            Filters
          </button>

          <Link
            to="/add-item"
            className="flex h-10 items-center gap-1.5 rounded-full bg-primary px-4 font-label text-label-sm text-on-primary shadow-sm transition-opacity hover:opacity-90"
          >
            <Plus size={18} aria-hidden="true" />
            Add Item
          </Link>
        </div>
      </div>

      <div className="mt-8 grid grid-cols-1 items-start gap-6 lg:grid-cols-12">
        <aside className={`${filtersOpen ? 'block' : 'hidden'} lg:sticky lg:top-20 lg:col-span-3 lg:block`}>
          <FilterSidebar
            categories={categories}
            activeCategory={category}
            onCategoryChange={setCategory}
            styleOptions={styleOptions}
            activeStyles={activeStyles}
            onToggleStyle={toggleStyle}
            colors={colors}
            activeColors={activeColors}
            onToggleColor={toggleColor}
            seasonOptions={SEASON_OPTIONS}
            activeSeason={season}
            onSeasonChange={setSeason}
            onReset={resetFilters}
          />
        </aside>

        <div className="space-y-4 lg:col-span-9">
          {activeChips.length > 0 && (
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-surface p-2 shadow-sm">
              <div className="flex flex-wrap items-center gap-2">
                <span className="pl-2 font-label-sm text-label-sm uppercase tracking-wider text-secondary">
                  Active:
                </span>
                {activeChips.map((chip) => (
                  <span
                    key={chip.key}
                    className="inline-flex items-center gap-1.5 rounded-full bg-canvas px-3 py-1 font-label text-label-sm text-primary"
                  >
                    {chip.label}
                    <button
                      type="button"
                      onClick={chip.onRemove}
                      aria-label={`Remove ${chip.label} filter`}
                      className="text-secondary hover:text-primary"
                    >
                      <X size={12} strokeWidth={2.5} aria-hidden="true" />
                    </button>
                  </span>
                ))}
              </div>
              <button
                type="button"
                onClick={clearAll}
                className="pr-2 font-label text-label-sm text-secondary transition-colors hover:text-primary"
              >
                Clear all
              </button>
            </div>
          )}

          {paginatedItems.length > 0 ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {paginatedItems.map((item) => (
                <ClothingCard
                  key={item.id}
                  item={item}
                  isFavorite={item.isFavorite ?? false}
                  onToggleFavorite={toggleFavorite}
                  isSelected={selectedId === item.id}
                  onSelect={(id) => setSelectedId((current) => (current === id ? null : id))}
                  onEdit={setEditingItem}
                  onDelete={setDeletingItem}
                />
              ))}
            </div>
          ) : (
            <div className="rounded-xl bg-surface p-12 text-center shadow-sm">
              <p className="font-heading text-h3 text-primary">No items match your filters</p>
              <p className="mt-1 font-body text-body-sm text-secondary">
                Try adjusting your search or clearing filters.
              </p>
              <button
                type="button"
                onClick={clearAll}
                className="mt-4 rounded-full bg-primary px-5 py-2 font-label text-label-sm text-on-primary transition-opacity hover:opacity-90"
              >
                Clear all filters
              </button>
            </div>
          )}

          <div className="flex flex-col items-center justify-between gap-2 rounded-xl bg-surface px-4 py-3 shadow-sm sm:flex-row">
            <p className="font-body text-body-sm text-secondary">
              Showing <span className="font-medium text-primary">{paginatedItems.length}</span> of{' '}
              <span className="font-medium text-primary">{sortedItems.length}</span> items
            </p>
            {totalPages > 1 && (
              <nav aria-label="Wardrobe pagination" className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                  aria-label="Previous page"
                  className="flex h-8 w-8 items-center justify-center rounded-full text-secondary transition-colors hover:bg-canvas disabled:opacity-40"
                >
                  <ChevronLeft size={18} aria-hidden="true" />
                </button>
                {Array.from({ length: totalPages }, (_, index) => index + 1).map((pageNumber) => (
                  <button
                    key={pageNumber}
                    type="button"
                    onClick={() => setPage(pageNumber)}
                    aria-current={currentPage === pageNumber ? 'page' : undefined}
                    className={`flex h-8 w-8 items-center justify-center rounded-full font-label text-label-sm transition-colors ${
                      currentPage === pageNumber ? 'bg-primary text-on-primary' : 'text-secondary hover:bg-canvas'
                    }`}
                  >
                    {pageNumber}
                  </button>
                ))}
                <button
                  type="button"
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
                  aria-label="Next page"
                  className="flex h-8 w-8 items-center justify-center rounded-full text-secondary transition-colors hover:bg-canvas disabled:opacity-40"
                >
                  <ChevronRight size={18} aria-hidden="true" />
                </button>
              </nav>
            )}
          </div>
        </div>
      </div>

      {editingItem && (
        <EditItemModal
          item={editingItem}
          onClose={() => setEditingItem(null)}
          onSaved={(updated) => {
            applyUpdatedItem(updated)
            setEditingItem(null)
          }}
        />
      )}

      {deletingItem && (
        <DeleteConfirmDialog item={deletingItem} onClose={() => setDeletingItem(null)} onDeleted={handleDeleted} />
      )}
    </section>
  )
}
