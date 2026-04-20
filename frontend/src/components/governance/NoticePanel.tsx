import type { ReactNode } from 'react'
import { ShieldAlert, UserRoundCheck } from 'lucide-react'

type Variant = 'confidential' | 'review'

const VARIANT_STYLES: Record<Variant, { wrap: string; icon: string; Icon: typeof ShieldAlert }> = {
  confidential: {
    wrap: 'notice-panel notice-panel-warn',
    icon: 'text-amber-600',
    Icon: ShieldAlert,
  },
  review: {
    wrap: 'notice-panel notice-panel-info',
    icon: 'text-sky-600',
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
    <div className={`${wrap} ${compact ? 'px-4 py-3' : 'px-5 py-4'}`}>
      <div className="flex items-start gap-3">
        <div className="notice-panel-icon-wrap">
          <Icon size={compact ? 15 : 16} className={`${icon} shrink-0`} />
        </div>
        <div>
          <div className="text-sm font-semibold text-slate-900">{title}</div>
          <div className="text-xs leading-relaxed mt-1 text-slate-600">{children}</div>
        </div>
      </div>
    </div>
  )
}
