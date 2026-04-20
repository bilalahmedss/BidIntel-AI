function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max)
}

export default function ScoreRing({
  value,
  total,
  label,
  sublabel,
  size = 184,
}: {
  value: number
  total: number
  label: string
  sublabel?: string
  size?: number
}) {
  const safeTotal = total > 0 ? total : 1
  const ratio = clamp(value / safeTotal, 0, 1)
  const stroke = 12
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  const dash = circumference * ratio

  return (
    <div className="score-ring" style={{ width: size, height: size }}>
      <svg width={size} height={size} role="img" aria-label={`${label}: ${value} out of ${total}`}>
        <defs>
          <linearGradient id="score-ring-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#2453ff" />
            <stop offset="100%" stopColor="#5d85ff" />
          </linearGradient>
        </defs>
        <circle className="score-ring-track" cx={size / 2} cy={size / 2} r={radius} strokeWidth={stroke} />
        <circle
          className="score-ring-fill"
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={stroke}
          strokeDasharray={`${dash} ${circumference}`}
        />
      </svg>
      <div className="score-ring-content">
        <div className="score-ring-value-row">
          <span className="score-ring-value">{Math.round(value)}</span>
          <span className="score-ring-total">/{Math.round(total)}</span>
        </div>
        <div className="score-ring-label">{label}</div>
        {sublabel && <div className="score-ring-sublabel">{sublabel}</div>}
      </div>
    </div>
  )
}
