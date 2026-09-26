/**
 * Handsome Dan logo: the real photo (public/handsome-dan.webp), cropped to a circle on his face
 * with a white ring. `size` is in px at the base 16px root; it's converted to rem so it scales
 * with the fluid root font size like the rest of the layout.
 */
export default function HandsomeDan({
  size = 40,
  animated = false,
  className = '',
}: {
  size?: number
  animated?: boolean
  className?: string
}) {
  const rem = size / 16
  return (
    <img
      src="/handsome-dan.webp"
      alt="Handsome Dan, the Yale bulldog"
      className={`dan-photo ${animated ? 'dan-animated' : ''} ${className}`}
      style={{ width: `${rem}rem`, height: `${rem}rem`, borderWidth: `${Math.max(1.5, size * 0.03) / 16}rem` }}
    />
  )
}
