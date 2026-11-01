---
name: Atelier Minimalist Fashion
colors:
  surface: '#f9f9fb'
  surface-dim: '#d9dadc'
  surface-bright: '#f9f9fb'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f3f3f5'
  surface-container: '#eeeef0'
  surface-container-high: '#e8e8ea'
  surface-container-highest: '#e2e2e4'
  on-surface: '#1a1c1d'
  on-surface-variant: '#46464b'
  inverse-surface: '#2f3132'
  inverse-on-surface: '#f0f0f2'
  outline: '#77767b'
  outline-variant: '#c7c6cb'
  surface-tint: '#5f5e61'
  primary: '#121315'
  on-primary: '#ffffff'
  primary-container: '#27272a'
  on-primary-container: '#8f8e91'
  inverse-primary: '#c8c6c9'
  secondary: '#5d5e66'
  on-secondary: '#ffffff'
  secondary-container: '#e3e1ec'
  on-secondary-container: '#63646c'
  tertiary: '#111315'
  on-tertiary: '#ffffff'
  tertiary-container: '#25272a'
  on-tertiary-container: '#8d8e91'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e4e1e5'
  primary-fixed-dim: '#c8c6c9'
  on-primary-fixed: '#1b1b1e'
  on-primary-fixed-variant: '#47464a'
  secondary-fixed: '#e3e1ec'
  secondary-fixed-dim: '#c6c5cf'
  on-secondary-fixed: '#1a1b22'
  on-secondary-fixed-variant: '#46464e'
  tertiary-fixed: '#e2e2e5'
  tertiary-fixed-dim: '#c6c6c9'
  on-tertiary-fixed: '#1a1c1e'
  on-tertiary-fixed-variant: '#454749'
  background: '#f9f9fb'
  on-background: '#1a1c1d'
  surface-variant: '#e2e2e4'
typography:
  display-hero:
    fontFamily: Plus Jakarta Sans
    fontSize: 56px
    fontWeight: '600'
    lineHeight: 64px
    letterSpacing: -0.03em
  display-hero-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 36px
    fontWeight: '600'
    lineHeight: 44px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 24px
    fontWeight: '500'
    lineHeight: 32px
    letterSpacing: -0.015em
  headline-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 20px
    fontWeight: '500'
    lineHeight: 28px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: DM Sans
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
    letterSpacing: 0em
  body-md:
    fontFamily: DM Sans
    fontSize: 15px
    fontWeight: '400'
    lineHeight: 24px
    letterSpacing: 0em
  body-sm:
    fontFamily: DM Sans
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
    letterSpacing: 0.005em
  label-lg:
    fontFamily: DM Sans
    fontSize: 15px
    fontWeight: '500'
    lineHeight: 20px
    letterSpacing: -0.005em
  label-md:
    fontFamily: DM Sans
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
    letterSpacing: 0em
  label-sm:
    fontFamily: DM Sans
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: 0.01em
rounded:
  sm: 0.5rem
  DEFAULT: 1rem
  md: 1.5rem
  lg: 2rem
  xl: 3rem
  full: 9999px
spacing:
  gutter: 1.5rem
  gutter-lg: 2.5rem
  margin: 1.25rem
  margin-md: 2.5rem
  margin-lg: 4rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2.5rem
---

## Brand & Style
The visual identity centers on restraint, quiet luxury, and gallery-level presentation for high-end fashion and lifestyle commerce. It strips away conventional retail noise—discount banners, artificial urgency counters, and dense product grids—in favor of generous negative space, sculptural silhouette framing, and effortless navigation.

Inspired by premium architectural lookbooks and Apple-level hardware presentation, the experience feels serene, tactile, and curated. Interfaces never compete with garments; rather, they serve as a canvas of warm-tinted light neutrals, allowing materials, drape, and texture to lead the dialogue.

- **Tone & Demeanor:** Restrained, elevated, tactile, and effortless.
- **Visual Style:** Modern High-Contrast Minimalism. Pure structural discipline, fluid pill contours, and delicate ambient light.
- **Copy & Voice:** Natural sentence case with understated cadence. Strictly avoid uppercase shouting, technical SKUs, or cluttering operational tags.

## Colors
The palette is rooted in tonal grayscale clarity, punctuated by absolute deep slate tones for focal actions.

- **Primary (`#27272A`):** The primary interaction anchor. Reserved for high-intent primary buttons, hero editorial titles, and definitive state transitions.
- **Secondary (`#71717A`):** Mid-tone neutral for editorial metadata, secondary navigation links, muted specifications, and inactive state cues.
- **Tertiary (`#E4E4E7`):** Hairline separation and soft boundary lines. Used sparingly to divide structural zones without breaking visual continuity.
- **Neutral Canvas (`#F4F4F6`):** The foundational ambient background. A muted, warm-cast gray that softens contrast and allows white surfaces to lift gracefully.
- **Surface Crisp (`#FFFFFF`):** Pure white designated exclusively for elevated cards, floating sheets, modals, and sticky action containers.

## Typography
Typography harmonizes clean geometric warmth (`Plus Jakarta Sans`) with fluid, low-contrast legibility (`DM Sans`). 

- Maintain standard sentence casing across all headlines, body copy, and UI controls.
- Letter tracking remains natural or slightly tight on display scales to create an editorial, tailored finish.
- Avoid uppercase tracking or industrial monospace treatments; hierarchy is achieved via size contrast and spatial isolation rather than exaggerated weights.

## Layout & Spacing
The layout system relies on a fluid grid bounded by generous exterior margins to evoke the breathing room of an art monograph.

- **Desktop Layout:** 12-column dynamic grid with a maximum content container width of 1440px. Gutters set to `gutter-lg` (2.5rem) to ensure imagery remains uncrowded.
- **Tablet Layout:** 8-column grid with `gutter` (1.5rem) and `margin-md` (2.5rem). Product feeds transition to dual-column cadence with heightened vertical offsets.
- **Mobile Layout:** 4-column structure with `margin` (1.25rem). Full-bleed image sliders and unified card modules prevent edge friction.
- **Vertical Rhythm:** Sections are separated by expansive vertical gaps (`space-xl` to double `space-xl`), allowing individual garment narratives to exist independently without layout collapse.

## Elevation & Depth
Depth is created through ambient, multi-stop diffusion rather than heavy drop shadows, preserving an airy, daylight-infused aesthetic.

- **Base Layer (0):** The `#F4F4F6` canvas forms the continuous foundation across screens.
- **Level 1 (Surface Cards & Panels):** Pure white (`#FFFFFF`) containers resting upon the gray ground. Elevation is rendered using a subtle ambient blur: `0 2px 8px -2px rgba(39, 39, 42, 0.04), 0 8px 24px -4px rgba(39, 39, 42, 0.06)`. No harsh perimeter borders.
- **Level 2 (Floating Controls & Dropdowns):** Interactive modals, filter sheets, and floating bottom bars: `0 12px 32px -6px rgba(39, 39, 42, 0.08), 0 4px 12px -2px rgba(39, 39, 42, 0.04)`.
- **Level 3 (Overlays & Dialogs):** Centered dialogs and active cart drawers paired with a blurred backdrop scrim (`backdrop-blur-md bg-neutral-900/10`).

## Shapes
The shape system pairs generous pill silhouettes for actionable elements with soft, structural curvature for presentation surfaces.

- **Action Elements (Buttons, Search Bars, Chips):** Fully rounded pill contours (`roundedness: 3` / `rounded-full`). These offer high organic contrast against rectangular garment photography.
- **Product & Content Containers:** `rounded-2xl` (1rem to 1.5rem radius) ensuring smooth corners that feel tailored and soft without losing architectural precision.
- **Media Assets:** Imagery adopts matching `rounded-2xl` corners or upper-corner radii when nested inside elevated white card shells.

## Components

### Buttons
- **Primary Pill:** Background `#27272A`, text `#FFFFFF`, fully rounded (`rounded-full`). Generous horizontal padding (e.g., `px-8 py-4`). Active states gently compress (`scale-[0.98]`).
- **Secondary Pill:** Background `#FFFFFF`, text `#27272A`, with a hairline border `#E4E4E7` or ambient Level 1 elevation.
- **Ghost Action:** Transparent background, text `#27272A`, subtle background shift to `#E4E4E7/50` on hover.

### Product & Editorial Cards
- Constructed on crisp `#FFFFFF` cards atop the `#F4F4F6` background.
- Subtle elevation via ambient diffusion (`shadow-sm` on rest, transitioning smoothly to `shadow-md` on hover).
- Generous internal padding (`space-md` to `space-lg`). Garment imagery maintains clean aspect ratios (3:4 or 4:5).

### Input Fields
- Enclosed within pill or soft rounded frames (`rounded-full` for search inputs, `rounded-xl` for complex forms).
- Background `#FFFFFF` with an inset boundary in `#E4E4E7`. 
- Focused state transitions to a solid `#27272A` ring (1px) with zero chromatic glow.

### Chips & Filter Pills
- Compact pill tokens (`rounded-full`, height 36px to 40px).
- Inactive: Background `#FFFFFF` with muted text `#71717A`.
- Active: Background `#27272A` with text `#FFFFFF` and smooth color transitions.

### Selection Controls (Checkboxes & Radios)
- Radios are concentric circles with an inner dot in `#27272A`.
- Checkboxes feature rounded corners (`rounded-md`), an active fill of `#27272A`, and a clean `#FFFFFF` check glyph.

### Floating Cart & Bottom Sheet
- Persistent floating pill bar or bottom-anchored modal sheet with frosted backing (`backdrop-blur-lg bg-white/90`).
- Provides quick-glance totals and frictionless single-tap checkout entry.