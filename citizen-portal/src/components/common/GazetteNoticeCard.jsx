import { FileText } from 'lucide-react'

const TAG_STYLES = {
  NOTICE: 'bg-brand-50 text-brand-700 border-brand-300',
  ADVISORY: 'bg-gold-100 text-gold-800 border-gold-400',
  BOARD: 'bg-emerald-50 text-govgreen border-emerald-300',
  ALERT: 'bg-slate-100 text-slateink border-slate-300',
}

export default function GazetteNoticeCard({ tag, title, date }) {
  const style = TAG_STYLES[tag] || TAG_STYLES.ALERT

  return (
    <div className="flex items-start gap-3 bg-white rounded-lg border border-slate-200 p-3.5 hover:shadow-gov transition-shadow">
      <span className="inline-flex items-center justify-center w-9 h-9 rounded-full bg-surface text-slate-500 shrink-0">
        <FileText className="w-4.5 h-4.5" strokeWidth={2} />
      </span>
      <div className="min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className={`text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded-full border ${style}`}>
            {tag}
          </span>
          <span className="text-[11px] text-slate-400">{date}</span>
        </div>
        <p className="text-sm font-medium text-slateink leading-snug">{title}</p>
      </div>
    </div>
  )
}
