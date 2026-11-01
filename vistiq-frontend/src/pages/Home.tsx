import { Camera, Shirt, Sparkles } from 'lucide-react'
import ActionCard from '../components/ActionCard'
import heroImage from '../assets/illustrations/hero-wardrobe.svg'
import topsImage from '../assets/illustrations/category-tops.svg'
import bottomsImage from '../assets/illustrations/category-bottoms.svg'
import footwearImage from '../assets/illustrations/category-footwear.svg'

const CURATED_CATEGORIES = [
  { label: 'Tops', image: topsImage, description: 'Shirts, tees & knitwear' },
  { label: 'Bottoms', image: bottomsImage, description: 'Trousers, denim & skirts' },
  { label: 'Footwear', image: footwearImage, description: 'Shoes, loafers & sneakers' },
]

export default function Home() {
  return (
    <>
      <section className="mx-auto max-w-6xl px-6 py-16 md:py-20">
        <div className="grid grid-cols-1 items-center gap-10 text-center lg:grid-cols-12 lg:gap-12 lg:text-left">
          <div className="lg:col-span-7">
            <span className="inline-flex items-center gap-2 rounded-full bg-surface px-4 py-1.5 font-label text-label-sm text-secondary shadow-sm">
              <span className="h-1.5 w-1.5 rounded-full bg-primary" aria-hidden="true" />
              Personal digital atelier
            </span>

            <h1 className="mx-auto mt-6 max-w-2xl font-heading text-hero-sm text-primary md:text-hero lg:mx-0">
              Your wardrobe. Smarter outfits.
            </h1>

            <p className="mx-auto mt-5 max-w-xl font-body text-body-lg text-secondary lg:mx-0">
              Effortless outfit recommendations from items you already own.
            </p>
          </div>

          <div className="lg:col-span-5">
            <div className="relative mx-auto aspect-[4/5] w-full max-w-sm overflow-hidden rounded-2xl shadow-md lg:max-w-none">
              <img
                src={heroImage}
                alt="A tailored blazer and folded knitwear arranged in an editorial flat lay"
                className="h-full w-full object-cover"
              />
            </div>
          </div>
        </div>

        <div className="mt-16 grid grid-cols-1 gap-6 text-left sm:grid-cols-2 lg:grid-cols-3">
          <ActionCard
            to="/wardrobe"
            title="My Wardrobe"
            description="Browse and manage your digitized closet"
            ctaLabel="View Items"
          >
            <div className="flex h-full w-full items-center justify-center">
              <Shirt size={40} strokeWidth={1.5} className="text-secondary" aria-hidden="true" />
            </div>
            <span className="absolute bottom-3 right-3 inline-flex items-center gap-1 rounded-full bg-surface/90 px-2.5 py-1 font-label-sm text-label-sm text-primary shadow-sm">
              <Shirt size={12} strokeWidth={2} aria-hidden="true" />
              Wardrobe
            </span>
          </ActionCard>

          <ActionCard
            to="/stylist"
            title="AI Stylist"
            description="Get personalized outfits for any occasion"
            ctaLabel="Get Started"
            emphasized
          >
            <div className="flex h-full w-full items-center justify-center bg-primary/5">
              <Sparkles size={40} strokeWidth={1.5} className="text-primary" aria-hidden="true" />
            </div>
            <span className="absolute left-3 top-3 inline-flex items-center gap-1.5 rounded-full bg-primary px-3 py-1 font-label-sm text-label-sm text-on-primary shadow-sm">
              <Sparkles size={12} strokeWidth={2} aria-hidden="true" />
              Curated Match
            </span>
          </ActionCard>

          <ActionCard
            to="/add-item"
            title="Add Clothing"
            description="Upload new garments"
            ctaLabel="Upload Photo"
          >
            <div className="flex h-full w-full flex-col items-center justify-center gap-1 p-6 text-center">
              <span className="mb-2 flex h-12 w-12 items-center justify-center rounded-full bg-surface text-primary shadow-sm transition-transform duration-300 group-hover:scale-110">
                <Camera size={22} strokeWidth={2} aria-hidden="true" />
              </span>
              <span className="font-label text-label text-primary">Quick digitizer</span>
              <span className="font-body text-body-sm text-secondary">Instant background extraction</span>
            </div>
          </ActionCard>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 pb-16 md:pb-24">
        <div className="text-center lg:text-left">
          <h2 className="font-heading text-h2 text-primary">Curated for your wardrobe</h2>
          <p className="mt-1 font-body text-body text-secondary">
            VistiQ recognizes garments across every category you own.
          </p>
        </div>

        <div className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-3">
          {CURATED_CATEGORIES.map(({ label, image, description }) => (
            <div
              key={label}
              className="group overflow-hidden rounded-2xl bg-surface shadow-sm transition-shadow duration-300 hover:shadow-md"
            >
              <div className="aspect-[4/5] w-full overflow-hidden bg-canvas">
                <img
                  src={image}
                  alt=""
                  aria-hidden="true"
                  loading="lazy"
                  className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                />
              </div>
              <div className="p-5">
                <h3 className="font-heading text-h3 text-primary">{label}</h3>
                <p className="mt-1 font-body text-body-sm text-secondary">{description}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <footer className="border-t border-border py-8">
        <p className="text-center font-body text-body-sm text-secondary">
          © 2025 VistiQ. All rights reserved.
        </p>
      </footer>
    </>
  )
}
