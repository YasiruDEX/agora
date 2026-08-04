import { Link, useLocation } from 'react-router-dom'
import { ChevronDown } from 'lucide-react'
import { DEPARTMENTS } from '../../mock/departmentData'
import { useLanguage } from '../../i18n/LanguageContext'

const NAV_KEY_BY_DEPT = {
  'contact-center': 'contactCenter',
  'social-services': 'socialServices',
  permits: 'permits',
  'tax-revenue': 'taxRevenue',
  records: 'records',
}

export default function Navigation() {
  const location = useLocation()
  const { t } = useLanguage()

  return (
    <nav className="bg-brand text-white">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <ul className="flex flex-wrap items-stretch">
          <li>
            <Link
              to="/"
              className={`inline-flex items-center h-11 px-4 text-sm font-semibold transition-colors ${
                location.pathname === '/' ? 'bg-brand-700' : 'hover:bg-brand-600'
              }`}
            >
              {t('nav.home')}
            </Link>
          </li>
          {DEPARTMENTS.map((dept) => (
            <li key={dept.id} className="group relative">
              <Link
                to={dept.route}
                className={`inline-flex items-center gap-1 h-11 px-4 text-sm font-semibold transition-colors ${
                  location.pathname === dept.route ? 'bg-brand-700' : 'hover:bg-brand-600'
                }`}
              >
                {t(`nav.${NAV_KEY_BY_DEPT[dept.id]}`)}
                <ChevronDown className="w-3 h-3 opacity-70" strokeWidth={2.5} />
              </Link>

              {/* Lightweight megamenu: department services, shown on hover/focus */}
              <div className="invisible opacity-0 group-hover:visible group-hover:opacity-100 group-focus-within:visible group-focus-within:opacity-100 transition-opacity absolute left-0 top-full z-30 w-72 bg-white text-slateink shadow-2xl rounded-b-lg border border-slate-200 border-t-0 overflow-hidden">
                <ul className="py-1.5">
                  {dept.services.map((svc) => (
                    <li key={svc.id}>
                      <Link to={dept.route} className="block px-4 py-2 hover:bg-surface">
                        <p className="text-sm font-semibold">{svc.title}</p>
                        <p className="text-xs text-slate-500">{svc.description}</p>
                      </Link>
                    </li>
                  ))}
                </ul>
                <Link to={dept.route} className="block px-4 py-2 text-xs font-semibold text-brand bg-surface hover:bg-slate-100 border-t border-slate-200">
                  {t('nav.viewServices')} →
                </Link>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </nav>
  )
}
