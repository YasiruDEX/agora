import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Phone, Search } from 'lucide-react'

const LANGUAGES = [
  { code: 'en', label: 'English' },
  { code: 'si', label: 'සිංහල' },
  { code: 'ta', label: 'தமிழ்' },
]

const STRINGS = {
  en: {
    portalName: 'Government of Sri Lanka',
    portalSub: 'Official Citizen Services Portal (Demo)',
    searchPlaceholder: 'Search for a service, department, or form...',
    hotlineLabel: 'Government Info Hotline',
  },
  si: {
    portalName: 'ශ්‍රී ලංකා ආණ්ඩුව',
    portalSub: 'නිල පුරවැසි සේවා ද්වාරය (නිරූපණය)',
    searchPlaceholder: 'සේවාවක්, දෙපාර්තමේන්තුවක් හෝ ආකෘතියක් සොයන්න...',
    hotlineLabel: 'රජයේ තොරතුරු දුරකථන අංකය',
  },
  ta: {
    portalName: 'இலங்கை அரசாங்கம்',
    portalSub: 'அதிகாரப்பூர்வ குடிமக்கள் சேவை போர்டல் (டெமோ)',
    searchPlaceholder: 'சேவை, திணைக்களம் அல்லது படிவத்தைத் தேடுங்கள்...',
    hotlineLabel: 'அரசாங்க தகவல் தொடர்பு எண்',
  },
}

export default function Header() {
  const [lang, setLang] = useState(() => localStorage.getItem('gov_lang') || 'en')
  const [search, setSearch] = useState('')

  useEffect(() => {
    localStorage.setItem('gov_lang', lang)
  }, [lang])

  const t = STRINGS[lang]

  return (
    <header className="sticky top-0 z-40 shadow-gov">
      {/* Top utility bar */}
      <div className="bg-slateink text-white text-xs">
        <div className="mx-auto max-w-7xl px-4 flex items-center justify-between h-9">
          <div className="flex items-center gap-1.5">
            {LANGUAGES.map((l) => (
              <button
                key={l.code}
                onClick={() => setLang(l.code)}
                className={`px-2 py-0.5 rounded transition-colors ${
                  lang === l.code ? 'bg-gold text-slateink font-semibold' : 'text-slate-200 hover:text-white'
                }`}
                aria-pressed={lang === l.code}
              >
                {l.label}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <span className="hidden sm:inline text-slate-300">{t.hotlineLabel}</span>
            <a
              href="tel:1919"
              className="inline-flex items-center gap-1.5 bg-maroon text-white font-bold px-2.5 py-0.5 rounded-full"
            >
              <Phone className="w-3 h-3" strokeWidth={2.5} />
              1919
            </a>
          </div>
        </div>
      </div>

      {/* Main header */}
      <div className="bg-white">
        <div className="mx-auto max-w-7xl px-4 py-3 flex items-center gap-4">
          <Link to="/" className="flex items-center gap-3 shrink-0">
            <img src="/images/emblem_sri_lanka.svg" alt="National Emblem of Sri Lanka (stylized, demo)" className="w-12 h-12" />
            <div className="leading-tight">
              <p className="font-bold text-slateink text-base sm:text-lg">{t.portalName}</p>
              <p className="text-[11px] sm:text-xs text-maroon font-medium">{t.portalSub}</p>
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
                placeholder={t.searchPlaceholder}
                className="w-full rounded-full border border-slate-300 bg-surface pl-4 pr-10 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gold focus:border-maroon"
              />
              <button
                type="submit"
                aria-label="Search"
                className="absolute right-1 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-maroon text-white flex items-center justify-center"
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
