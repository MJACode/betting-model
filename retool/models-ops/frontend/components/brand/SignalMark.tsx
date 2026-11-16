/**
 * The SignalBase mark: the stepped "S" on its amber ground, drawn from the
 * geometry in scripts/render_brand_icons.py (three bars 48 units thick, two
 * 36-unit gaps, on a 216-unit side; the S fills 54% of the tile). One path, so
 * it stays crisp at any size.
 */
const S_PATH = 'M0 0H216V48H48V84H216V216H0V168H168V132H0Z'

export function SignalMark({ size = 28, className }: { size?: number; className?: string }) {
  // 216 / 0.54 = 400: the tile is 400 units, the S 216 of them, as in the icon.
  const inset = 92
  return (
    <svg
      width={size}
      height={size}
      viewBox={`${-inset} ${-inset} ${216 + 2 * inset} ${216 + 2 * inset}`}
      className={className}
      role="img"
      aria-label="SignalBase"
    >
      <rect
        x={-inset}
        y={-inset}
        width={216 + 2 * inset}
        height={216 + 2 * inset}
        rx={(216 + 2 * inset) * 0.2}
        fill="#F2B01E"
      />
      <path d={S_PATH} fill="#0B1320" />
    </svg>
  )
}

/** Mark, wordmark and product name, for the navy header. */
export function BrandLockup({ product = 'Ops' }: { product?: string }) {
  return (
    <div className="flex items-center gap-3">
      <SignalMark size={30} />
      <div className="flex items-center gap-3">
        <span className="sb-wordmark hidden sm:inline">SIGNALBASE</span>
        <span className="hidden h-4 w-px bg-white/15 sm:inline-block" aria-hidden />
        <span className="sb-product">{product}</span>
      </div>
    </div>
  )
}
