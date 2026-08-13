import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Phone, Search } from 'lucide-react'
import { useLanguage } from '../../i18n/LanguageContext'

export default function Header() {
  const { t } = useLanguage()
  const [search, setSearch] = useState('')

  return (
    <header className="sticky top-0 z-40 shadow-gov">
      {/* Top utility bar */}
      <div className="bg-slateink text-white text-xs">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 flex items-center justify-end h-9">
          <div className="flex items-center gap-2">
            <span className="hidden sm:inline text-slate-300">{t('header.hotlineLabel')}</span>
            <a
              href="tel:311"
              className="inline-flex items-center gap-1.5 bg-brand text-white font-bold px-2.5 py-0.5 rounded-full"
            >
              <Phone className="w-3 h-3" strokeWidth={2.5} />
              311
            </a>
          </div>
        </div>
      </div>

      {/* Main header */}
      <div className="bg-white">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-3 flex items-center gap-4">
          <Link to="/" className="flex items-center gap-3 shrink-0">
            <img src="/images/emblem_riverside_county.svg" alt="Riverside County Seal (stylized, demo)" className="w-12 h-12" />
            <div className="leading-tight">
              <p className="font-bold text-slateink text-base sm:text-lg">{t('header.portalName')}</p>
              <p className="text-[11px] sm:text-xs text-brand font-medium">{t('header.portalSub')}</p>
            </div>
          </Link>

          <form
            className="flex-1 max-w-xl ml-auto hidden md:flex"
            onSubmit={(e) => e.preventDefault()}
            role="search"
          >
            <div className="relative w-full">
              <input
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={t('header.searchPlaceholder')}
                className="w-full rounded-full border border-slate-300 bg-surface pl-4 pr-10 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gold focus:border-brand"
              />
              <button
                type="submit"
                aria-label="Search"
                className="absolute right-1 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-brand text-white flex items-center justify-center"
              >
                <Search className="w-4 h-4" strokeWidth={2} />
              </button>
            </div>
          </form>
        </div>
      </div>
    </header>
  )
}
