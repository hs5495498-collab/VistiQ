import { Check } from 'lucide-react'

export interface CategoryOption {
  label: string
  count: number
}

export interface ColorOption {
  name: string
  count: number
  swatch: string
}

interface FilterSidebarProps {
  categories: CategoryOption[]
  activeCategory: string
  onCategoryChange: (category: string) => void

  styleOptions: string[]
  activeStyles: string[]
  onToggleStyle: (style: string) => void

  colors: ColorOption[]
  activeColors: string[]
  onToggleColor: (color: string) => void

  seasonOptions: string[]
  activeSeason: string
  onSeasonChange: (season: string) => void

  onReset: () => void
}

function CheckboxRow({
  label,
  count,
  active,
  onClick,
}: {
  label: string
  count?: number
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className="group flex w-full items-center justify-between rounded-lg p-1.5 text-left transition-colors hover:bg-canvas"
    >
      <span className="flex items-center gap-2.5">
        <span
          className={`flex h-4 w-4 items-center justify-center rounded ${
            active ? 'bg-primary text-on-primary' : 'bg-border/70 group-hover:bg-border'
          }`}
          aria-hidden="true"
        >
          {active && <Check size={12} strokeWidth={3} />}
        </span>
        <span className={`font-body text-body-sm ${active ? 'font-medium text-primary' : 'text-secondary group-hover:text-primary'}`}>
          {label}
        </span>
      </span>
      {typeof count === 'number' && (
        <span className="rounded-full bg-canvas px-2 py-0.5 font-label-sm text-label-sm text-secondary">
          {count}
        </span>
      )}
    </button>
  )
}

export default function FilterSidebar({
  categories,
  activeCategory,
  onCategoryChange,
  styleOptions,
  activeStyles,
  onToggleStyle,
  colors,
  activeColors,
  onToggleColor,
  seasonOptions,
  activeSeason,
  onSeasonChange,
  onReset,
}: FilterSidebarProps) {
  return (
    <div className="space-y-6 rounded-xl bg-surface p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <h2 className="font-heading text-h3 text-primary">Filter Collection</h2>
        <button
          type="button"
          onClick={onReset}
          className="font-label-sm text-label-sm text-secondary transition-colors hover:text-primary"
        >
          Reset All
        </button>
      </div>

      <div className="space-y-2">
        <p className="font-label-sm text-label-sm uppercase tracking-wider text-secondary">Categories</p>
        <div className="space-y-1">
          {categories.map(({ label, count }) => (
            <CheckboxRow
              key={label}
              label={label}
              count={count}
              active={activeCategory === label}
              onClick={() => onCategoryChange(label)}
            />
          ))}
        </div>
      </div>

      <div className="space-y-2">
        <p className="font-label-sm text-label-sm uppercase tracking-wider text-secondary">Style Archetype</p>
        <div className="flex flex-wrap gap-1.5">
          {styleOptions.map((style) => {
            const active = activeStyles.includes(style)
            return (
              <button
                key={style}
                type="button"
                onClick={() => onToggleStyle(style)}
                aria-pressed={active}
                className={`h-7 rounded-full px-3 font-label text-label-sm transition-colors ${
                  active ? 'bg-primary text-on-primary' : 'bg-canvas text-secondary hover:text-primary'
                }`}
              >
                {style}
              </button>
            )
          })}
        </div>
      </div>

      <div className="space-y-2">
        <p className="font-label-sm text-label-sm uppercase tracking-wider text-secondary">Palette</p>
        <div className="space-y-1.5">
          {colors.map(({ name, count, swatch }) => {
            const active = activeColors.includes(name)
            return (
              <button
                key={name}
                type="button"
                onClick={() => onToggleColor(name)}
                aria-pressed={active}
                className={`flex w-full items-center justify-between rounded-lg p-1.5 text-left transition-colors hover:bg-canvas ${
                  active ? 'bg-canvas' : ''
                }`}
              >
                <span className="flex items-center gap-2.5">
                  <span
                    className="h-3 w-3 rounded-full border border-border"
                    style={{ backgroundColor: swatch }}
                    aria-hidden="true"
                  />
                  <span className={`font-body text-body-sm ${active ? 'font-medium text-primary' : 'text-secondary'}`}>
                    {name}
                  </span>
                </span>
                <span className="rounded-full bg-canvas px-2 py-0.5 font-label-sm text-label-sm text-secondary">
                  {count}
                </span>
              </button>
            )
          })}
        </div>
      </div>

      <div className="space-y-2">
        <p className="font-label-sm text-label-sm uppercase tracking-wider text-secondary">Weather Season</p>
        <div className="space-y-1">
          {seasonOptions.map((season) => (
            <CheckboxRow
              key={season}
              label={season}
              active={activeSeason === season}
              onClick={() => onSeasonChange(season)}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
