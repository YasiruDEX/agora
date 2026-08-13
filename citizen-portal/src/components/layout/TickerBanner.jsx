import { Megaphone } from 'lucide-react'
import { useLanguage } from '../../i18n/LanguageContext'

export default function TickerBanner() {
  const { t } = useLanguage()
  const items = t('ticker.items')
  const label = t('ticker.label')
  // Duplicate the sequence so the CSS scroll loop has no visible seam.
  const looped = [...items, ...items]

  return (
    <div className="bg-gold-100 border-b border-gold-300 overflow-hidden">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 flex items-center h-8 gap-3">
        <span className="shrink-0 inline-flex items-center gap-1 text-[11px] font-bold text-brand uppercase tracking-wide">
          <Megaphone className="w-3.5 h-3.5" strokeWidth={2.5} />
          {label}
        </span>
        <div className="relative flex-1 overflow-hidden h-full">
          <div className="absolute whitespace-nowrap flex items-center h-full gap-10 gov-ticker-track">
            {looped.map((item, i) => (
              <span key={i} className="text-xs text-gold-900 font-medium">
                {item}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
