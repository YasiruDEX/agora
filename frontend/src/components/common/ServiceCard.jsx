import { Link } from 'react-router-dom'

const COLOR_ACCENTS = {
  maroon: 'border-t-maroon',
  gold: 'border-t-gold',
  govgreen: 'border-t-govgreen',
}

const ICON_BG = {
  maroon: 'bg-maroon-50 text-maroon-700',
  gold: 'bg-gold-100 text-gold-800',
  govgreen: 'bg-emerald-50 text-govgreen',
}

export default function ServiceCard({ title, description, to, color = 'maroon', Icon }) {
  return (
    <Link
      to={to}
      className={`group block bg-white rounded-lg border border-slate-200 border-t-4 ${COLOR_ACCENTS[color] || COLOR_ACCENTS.maroon} p-4 shadow-sm hover:shadow-gov transition-shadow`}
    >
      <div className="flex items-start gap-3">
        {Icon && (
          <span className={`inline-flex items-center justify-center w-9 h-9 rounded-full shrink-0 ${ICON_BG[color] || ICON_BG.maroon}`}>
            <Icon className="w-5 h-5" strokeWidth={2} />
          </span>
        )}
        <div>
          <p className="font-semibold text-slateink group-hover:text-maroon transition-colors">{title}</p>
          {description && <p className="text-sm text-slate-500 mt-1">{description}</p>}
        </div>
      </div>
    </Link>
  )
}
