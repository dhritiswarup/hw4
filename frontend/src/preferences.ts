import { useSyncExternalStore } from 'react'

/** Shopper's "My size" filter, remembered across visits in localStorage and shared by every component. */

export const SIZES = ['XS', 'S', 'M', 'L', 'XL', 'XXL'] as const
export type Size = (typeof SIZES)[number]

const KEY = 'cc.preferredSize'
const EVENT = 'cc:preferred-size'

function read(): Size | null {
  const v = localStorage.getItem(KEY)
  return (SIZES as readonly string[]).includes(v ?? '') ? (v as Size) : null
}

function subscribe(onChange: () => void) {
  window.addEventListener(EVENT, onChange)
  window.addEventListener('storage', onChange) // other tabs
  return () => {
    window.removeEventListener(EVENT, onChange)
    window.removeEventListener('storage', onChange)
  }
}

export function setPreferredSize(size: Size | null) {
  if (size) localStorage.setItem(KEY, size)
  else localStorage.removeItem(KEY)
  window.dispatchEvent(new Event(EVENT))
}

export function usePreferredSize(): [Size | null, (size: Size | null) => void] {
  return [useSyncExternalStore(subscribe, read), setPreferredSize]
}
