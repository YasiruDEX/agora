import ReactMarkdown from 'react-markdown'
import { CheckCircle, ShieldAlert, FileText, Wallet, Receipt, ClipboardList, Loader2 } from 'lucide-react'
import { useLanguage } from '../../i18n/LanguageContext'

const BADGE_STYLES = {
  emerald: 'bg-emerald-50 border-emerald-300 text-emerald-800',
  brand: 'bg-brand-50 border-brand-300 text-brand-700',
  gold: 'bg-gold-50 border-gold-400 text-gold-800',
}

const STATUS_PILL = {
  emerald: 'bg-emerald-600 text-white',
  brand: 'bg-brand text-white',
  gold: 'bg-gold-500 text-slateink',
}

const CARD_ICONS = {
  eligibility: CheckCircle,
  'case-summary': ClipboardList,
  'security-notice': ShieldAlert,
  'application-status': ClipboardList,
  payment: Wallet,
  receipt: Receipt,
  'redacted-record': FileText,
  'exemption-notice': ShieldAlert,
}

function AgentCard({ card, onAction, actionLoading }) {
  const { t } = useLanguage()
  const palette = BADGE_STYLES[card.badgeColor] || BADGE_STYLES.emerald
  const pill = STATUS_PILL[card.badgeColor] || STATUS_PILL.emerald
  const Icon = CARD_ICONS[card.type] || FileText

  return (
    <div className={`mt-2 rounded-lg border ${palette} p-3 text-sm`}>
      <div className="flex items-center justify-between gap-2 mb-2">
        <p className="font-bold flex items-center gap-1.5">
          <Icon className="w-4 h-4 shrink-0" strokeWidth={2} />
          {card.title}
        </p>
        {card.status && <span className={`text-[11px] font-bold px-2 py-0.5 rounded-full ${pill}`}>{card.status}</span>}
      </div>
      <dl className="space-y-1">
        {card.fields.map((f) => (
          <div key={f.label} className="flex gap-2">
            <dt className="min-w-[9rem] shrink-0 text-slate-500 font-medium">{f.label}</dt>
            <dd className="text-slateink break-words">{f.value}</dd>
          </div>
        ))}
      </dl>
      {card.actions?.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {card.actions.map((action) => (
            <button
              key={action.id}
              disabled={actionLoading}
              onClick={() => onAction?.(action.id)}
              className="inline-flex items-center gap-1.5 bg-brand hover:bg-brand-600 disabled:opacity-60 text-white text-xs font-semibold px-3 py-1.5 rounded-full transition-colors"
            >
              {actionLoading && <Loader2 className="w-3 h-3 animate-spin" strokeWidth={2.5} />}
              {actionLoading ? t('chat.processing') : action.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default function ChatMessage({ role, text, card, steps, onAction, actionLoading }) {
  const isUser = role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm shadow-sm animate-gov-fade-in ${
          isUser ? 'bg-brand text-white rounded-br-sm' : 'bg-white border border-slate-200 text-slateink rounded-bl-sm'
        }`}
      >
        {!isUser && steps?.length > 0 && (
          <div className="mb-1.5 space-y-0.5">
            {steps.map((step, i) => (
              <p key={i} className="text-[11px] text-slate-400 italic flex items-center gap-1">
                <span className="inline-block w-1 h-1 rounded-full bg-slate-400" />
                {step}
              </p>
            ))}
          </div>
        )}

        {isUser ? (
          <p className="whitespace-pre-wrap">{text}</p>
        ) : (
          <div className="prose-chat">
            <ReactMarkdown>{text}</ReactMarkdown>
          </div>
        )}

        {card && <AgentCard card={card} onAction={onAction} actionLoading={actionLoading} />}
      </div>
    </div>
  )
}
