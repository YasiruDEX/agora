import { useLanguage } from '../../i18n/LanguageContext'

/**
 * Shows the human officer persona "assisting" the active agent session,
 * alongside the department seal — reinforces that every AI agent in this
 * demo is framed as working under a named officer's supervision.
 */
export default function OfficerBadge({ persona, seal, department }) {
  const { t } = useLanguage()
  if (!persona) return null

  const designation = t(`officers.designations.${persona.designationKey}`)

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 bg-white/10 rounded-lg">
      {seal && <img src={seal} alt="" className="w-6 h-6 rounded-full shrink-0" />}
      <div className="leading-tight min-w-0">
        <p className="text-[11px] text-white/60">
          {t('chat.assistedBy')} <span className="text-white font-semibold">{persona.name}</span>
        </p>
        <p className="text-[10px] text-white/50 truncate">
          {designation}
          {department ? ` · ${department}` : ''}
        </p>
      </div>
    </div>
  )
}
