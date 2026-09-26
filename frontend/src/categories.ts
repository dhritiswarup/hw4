import type { Product } from './api'

// garment_type has ~22 raw variants; group them into shopper-friendly categories (first match wins,
// so a "crew-neck t-shirt" counts once). Mirrors backend tools.CATEGORIES.
export const CATEGORIES: { label: string; match: RegExp }[] = [
  { label: 'Hoodies', match: /hood/i },
  { label: 'Crewnecks', match: /crew(neck)?|mockneck/i },
  { label: 'T-shirts', match: /t-shirt|performance shirt/i },
  { label: 'Quarter-zips', match: /quarter-zip/i },
  { label: 'Jackets', match: /jacket/i },
]

export function categoryOf(p: Product) {
  return CATEGORIES.find((c) => c.match.test(p.garment_type))?.label ?? 'Other'
}
