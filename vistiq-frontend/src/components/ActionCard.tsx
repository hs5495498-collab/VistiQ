import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'

interface ActionCardProps {
  to: string
  title: string
  description: string
  ctaLabel: string
  emphasized?: boolean
  children: ReactNode
}

export default function ActionCard({
  to,
  title,
  description,
  ctaLabel,
  emphasized = false,
  children,
}: ActionCardProps) {
  return (
    <div
      className={`group flex flex-col justify-between rounded-lg bg-surface p-7 shadow-sm transition-shadow duration-300 hover:shadow-md ${
        emphasized ? 'shadow-md' : ''
      }`}
    >
      <div>
        <div className="relative mb-6 h-44 w-full overflow-hidden rounded-md bg-canvas">
          {children}
        </div>
        <h2 className="font-heading text-h3 text-primary">{title}</h2>
        <p className="mt-1 font-body text-body-sm text-secondary">{description}</p>
      </div>

      <Link
        to={to}
        className={`mt-8 flex w-full items-center justify-center gap-1.5 rounded-full px-5 py-3 font-label text-label transition-all active:scale-[0.98] ${
          emphasized
            ? 'bg-primary text-on-primary shadow-sm hover:opacity-90'
            : 'bg-canvas text-primary hover:bg-border'
        }`}
      >
        <span>{ctaLabel}</span>
        <ArrowRight
          size={16}
          strokeWidth={2}
          aria-hidden="true"
          className="transition-transform duration-200 group-hover:translate-x-0.5"
        />
      </Link>
    </div>
  )
}
