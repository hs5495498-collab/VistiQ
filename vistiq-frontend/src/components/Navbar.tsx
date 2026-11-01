import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { Home, Shirt, PlusSquare, Sparkles, Wand2, Menu, X } from 'lucide-react'

const NAV_LINKS = [
  { to: '/', label: 'Home', icon: Home, end: true },
  { to: '/wardrobe', label: 'My Wardrobe', icon: Shirt },
  { to: '/add-item', label: 'Add Item', icon: PlusSquare },
  { to: '/stylist', label: 'AI Stylist', icon: Sparkles },
  { to: '/recommendations', label: 'Recommendations', icon: Wand2 },
]

function linkClasses(isActive: boolean) {
  return [
    'flex items-center gap-2 rounded-full px-4 py-2 font-body text-body-sm transition-colors',
    isActive
      ? 'bg-primary text-on-primary'
      : 'text-secondary hover:bg-canvas hover:text-primary',
  ].join(' ')
}

export default function Navbar() {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <header className="sticky top-0 z-50 border-b border-border bg-surface/80 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        <NavLink
          to="/"
          className="font-heading text-h3 tracking-tight text-primary"
          onClick={() => setIsOpen(false)}
        >
          VistiQ
        </NavLink>

        <nav className="hidden items-center gap-1 md:flex" aria-label="Primary">
          {NAV_LINKS.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} className={({ isActive }) => linkClasses(isActive)}>
              <Icon size={16} strokeWidth={2} aria-hidden="true" />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <button
          type="button"
          className="flex h-10 w-10 items-center justify-center rounded-full text-primary transition-colors hover:bg-canvas md:hidden"
          aria-label={isOpen ? 'Close navigation menu' : 'Open navigation menu'}
          aria-expanded={isOpen}
          onClick={() => setIsOpen((open) => !open)}
        >
          {isOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      {isOpen && (
        <nav
          className="flex flex-col gap-1 border-t border-border bg-surface px-4 py-3 md:hidden"
          aria-label="Primary"
        >
          {NAV_LINKS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              onClick={() => setIsOpen(false)}
              className={({ isActive }) => linkClasses(isActive)}
            >
              <Icon size={16} strokeWidth={2} aria-hidden="true" />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
      )}
    </header>
  )
}
