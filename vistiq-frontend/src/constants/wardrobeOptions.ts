import type { ClothingCategory, ClothingStyle, Occasion, Season } from '../types/clothing'

/**
 * Single source of truth for the vocabularies used by both Add Item and
 * Edit Item, so the two forms can never drift apart into offering
 * incompatible values for the same backend fields.
 */

export const CATEGORY_OPTIONS: ClothingCategory[] = ['Tops', 'Bottoms', 'Outerwear', 'Footwear', 'Accessories', 'Dresses']
export const STYLE_OPTIONS: ClothingStyle[] = ['Casual', 'Smart Casual', 'Minimal', 'Streetwear', 'Formal', 'Sporty']
export const OCCASION_OPTIONS: Occasion[] = ['Casual', 'College', 'Office', 'Party', 'Formal', 'Date']
export const SEASON_OPTIONS: Season[] = ['All Season', 'Warm Weather', 'Cool Weather', 'Layering Pieces']

// Mirrors ml/labels/clothing_categories.json's color_palette.buckets exactly,
// so every color the AI suggestion / color.py can return is selectable here.
export const COLOR_OPTIONS: { name: string; swatch: string }[] = [
  { name: 'Black', swatch: '#18181b' },
  { name: 'White', swatch: '#f4f4f5' },
  { name: 'Grey', swatch: '#9ca3af' },
  { name: 'Navy', swatch: '#243b55' },
  { name: 'Indigo', swatch: '#3c4a75' },
  { name: 'Beige', swatch: '#d9cdb8' },
  { name: 'Brown', swatch: '#6b4a34' },
  { name: 'Green', swatch: '#3f6c4f' },
  { name: 'Blue', swatch: '#3b6cbf' },
  { name: 'Red', swatch: '#b22a2a' },
  { name: 'Yellow', swatch: '#d6b83c' },
  { name: 'Pink', swatch: '#d691a8' },
  { name: 'Purple', swatch: '#6e4891' },
  { name: 'Orange', swatch: '#c96f35' },
]

/** Swatches light enough that a dark checkmark reads better than a white one. */
export const LIGHT_COLOR_NAMES = new Set(['White', 'Beige', 'Yellow'])
