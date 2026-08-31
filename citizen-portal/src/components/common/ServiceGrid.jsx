import { Link } from 'react-router-dom'
import { Phone, HeartHandshake, Building2, Landmark, FileText } from 'lucide-react'
import { useLanguage } from '../../i18n/LanguageContext'

// One category per department this portal actually serves — matches the 5 Citizen Inquiry
// Agent instances (PLAN.md §5/§6), not an aspirational full service catalog.
const CATEGORY_ICONS = {
  'contact-center': Phone,
  social: HeartHandshake,
  permits: Building2,
  tax: Landmark,
  records: FileText,
}

const CATEGORY_ROUTES = {
  'contact-center': '/contact-center',
  social: '/social-services',
  permits: '/permits',
  tax: '/tax-revenue',
  records: '/records',
}

export default function ServiceGrid() {
  const { t } = useLanguage()
  const categories = t('serviceGrid.categories')

  return (
    <section>
      <div className="flex items-baseline justify-between mb-1">
        <h2 className="text-xl font-bold text-slateink">{t('serviceGrid.title')}</h2>
      </div>
      <p className="text-sm text-slate-500 mb-4">{t('serviceGrid.subtitle')}</p>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {categories.map((cat) => {
          const Icon = CATEGORY_ICONS[cat.id] || FileText
          const route = CATEGORY_ROUTES[cat.id]
          const cardClass = `bg-white rounded-lg border border-slate-200 p-3.5 flex flex-col gap-2 ${
            route ? 'hover:shadow-gov hover:border-brand transition-all cursor-pointer' : 'opacity-90'
          }`
          const content = (
            <>
              <span className="inline-flex items-center justify-center w-9 h-9 rounded-full bg-brand-50 text-brand-700">
                <Icon className="w-4.5 h-4.5" strokeWidth={2} />
              </span>
              <div>
                <p className="font-semibold text-sm text-slateink leading-tight">{cat.title}</p>
                <p className="text-xs text-slate-500 mt-0.5">{cat.description}</p>
              </div>
            </>
          )
          return route ? (
            <Link key={cat.id} to={route} className={cardClass}>
              {content}
            </Link>
          ) : (
            <div key={cat.id} className={cardClass}>
              {content}
            </div>
          )
        })}
      </div>
    </section>
  )
}
