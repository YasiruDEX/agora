import { CheckCircle, ShieldAlert } from 'lucide-react'
import { useLanguage } from '../../i18n/LanguageContext'

export default function DepartmentBadge({ department, agentName, tier }) {
  const { t } = useLanguage()
  const TierIcon = tier?.key === 'onprem' ? ShieldAlert : CheckCircle

  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="leading-tight">
        <p className="text-white font-semibold text-sm">{agentName}</p>
        <p className="text-white/70 text-xs">{department}</p>
      </div>
      {tier && (
        <span
          className={`ml-auto inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full border ${tier.className}`}
          title={
            tier.key === 'onprem'
              ? 'This agent runs on an on-prem model because it handles sensitive citizen data.'
              : 'This agent runs on a cloud model.'
          }
        >
          <TierIcon className="w-3 h-3" strokeWidth={2.5} />
          {tier.key === 'onprem' ? t('chat.onPremBadge') : t('chat.cloudBadge')}
        </span>
      )}
    </div>
  )
}
