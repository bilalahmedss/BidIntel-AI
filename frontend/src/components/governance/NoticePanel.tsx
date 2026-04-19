import type { ReactNode } from 'react'
import { ShieldAlert, UserRoundCheck } from 'lucide-react'

type Variant = 'confidential' | 'review'

const VARIANT_STYLES: Record<Variant, { wrap: string; icon: string; Icon: typeof ShieldAlert }> = {
  confidential: {
    wrap: 'bg-amber-950/40 border-amber-800 text-amber-100',
    icon: 'text-amber-400',
    Icon: ShieldAlert,
  },
  review: {
    wrap: 'bg-sky-950/40 border-sky-800 text-sky-100',
    icon: 'text-sky-400',
    Icon: UserRoundCheck,
  },
}

export default function NoticePanel({
  variant,
  title,
  children,
  compact = false,
}: {
  variant: Variant
  title: string
  children: ReactNode
  compact?: boolean
}) {
  const { wrap, icon, Icon } = VARIANT_STYLES[variant]
  return (
    <div className={`border rounded-xl ${compact ? 'px-4 py-3' : 'px-4 py-4'} ${wrap}`}>
      <div className="flex items-start gap-3">
        <Icon size={compact ? 16 : 18} className={`${icon} shrink-0 mt-0.5`} />
        <div>
          <div className="text-sm font-semibold">{title}</div>
          <div className="text-xs leading-relaxed mt-1 text-slate-200">{children}</div>
        </div>
      </div>
    </div>
  )
}
