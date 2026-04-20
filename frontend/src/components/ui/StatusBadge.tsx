import type { ReactNode } from 'react'

type Tone = 'neutral' | 'info' | 'success' | 'warn' | 'danger'

const TONE_CLASS: Record<Tone, string> = {
  neutral: 'ui-badge ui-badge-neutral',
  info: 'ui-badge ui-badge-info',
  success: 'ui-badge ui-badge-success',
  warn: 'ui-badge ui-badge-warn',
  danger: 'ui-badge ui-badge-danger',
}

export default function StatusBadge({
  tone = 'neutral',
  children,
  className = '',
}: {
  tone?: Tone
  children: ReactNode
  className?: string
}) {
  return <span className={[TONE_CLASS[tone], className].filter(Boolean).join(' ')}>{children}</span>
}
