import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Landmark, HeartHandshake, Building2, FileSearch, ChevronLeft, ChevronRight } from 'lucide-react'
import { useLanguage } from '../../i18n/LanguageContext'

const IMAGE_MAP = {
  secretariat: '/images/hero_secretariat.svg',
  parliament: '/images/hero_parliament.svg',
  treasury: '/images/hero_treasury.svg',
  municipal: '/images/hero_municipal.svg',
}

const AUTOPLAY_MS = 6500

export default function HeroCarousel() {
  const { t } = useLanguage()
  const slides = t('hero.slides')
  const actions = t('hero.actions')
  const [index, setIndex] = useState(0)
  const [search, setSearch] = useState('')

  useEffect(() => {
    setIndex(0)
  }, [slides.length])

  useEffect(() => {
    const id = setInterval(() => setIndex((i) => (i + 1) % slides.length), AUTOPLAY_MS)
    return () => clearInterval(id)
  }, [slides.length])

  const slide = slides[index] || slides[0]

  const quickActions = [
    { key: 'payRates', to: '/tax-revenue', Icon: Landmark },
    { key: 'checkBenefits', to: '/social-services', Icon: HeartHandshake },
    { key: 'trackPermit', to: '/permits', Icon: Building2 },
    { key: 'requestFoia', to: '/records', Icon: FileSearch },
  ]

  return (
    <section className="relative overflow-hidden bg-slateink text-white">
      <div className="relative h-[380px] sm:h-[440px]">
        {slides.map((s, i) => (
          <div
            key={i}
            aria-hidden={i !== index}
            className="absolute inset-0 transition-opacity duration-700 ease-out"
            style={{ opacity: i === index ? 1 : 0, pointerEvents: i === index ? 'auto' : 'none' }}
          >
            <img
              src={IMAGE_MAP[s.image] || IMAGE_MAP.secretariat}
              alt=""
              className="absolute inset-0 w-full h-full object-cover"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-slateink via-slateink/60 to-slateink/20" />
          </div>
        ))}

        <div className="relative h-full mx-auto max-w-7xl px-4 flex flex-col justify-center">
          <p className="uppercase tracking-widest text-gold text-xs font-bold mb-3">{t('hero.kicker')}</p>
          <h1 className="text-3xl sm:text-4xl font-extrabold mb-3 max-w-2xl">{slide.title}</h1>
          <p className="text-white/85 max-w-2xl mb-7">{slide.subtitle}</p>

          <form className="max-w-xl flex" onSubmit={(e) => e.preventDefault()}>
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t('hero.searchPlaceholder')}
              className="flex-1 rounded-l-full px-5 py-3 text-slateink text-sm focus:outline-none focus:ring-2 focus:ring-gold"
            />
            <button type="submit" className="bg-gold hover:bg-gold-500 text-slateink font-bold px-6 rounded-r-full text-sm">
              {t('hero.searchButton')}
            </button>
          </form>
        </div>

        {/* Prev/next controls */}
        <button
          onClick={() => setIndex((i) => (i - 1 + slides.length) % slides.length)}
          aria-label="Previous slide"
          className="absolute left-3 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-black/30 hover:bg-black/50 flex items-center justify-center"
        >
          <ChevronLeft className="w-5 h-5" strokeWidth={2.5} />
        </button>
        <button
          onClick={() => setIndex((i) => (i + 1) % slides.length)}
          aria-label="Next slide"
          className="absolute right-3 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-black/30 hover:bg-black/50 flex items-center justify-center"
        >
          <ChevronRight className="w-5 h-5" strokeWidth={2.5} />
        </button>

        {/* Dots */}
        <div className="absolute bottom-3 left-1/2 -translate-x-1/2 flex gap-1.5">
          {slides.map((_, i) => (
            <button
              key={i}
              onClick={() => setIndex(i)}
              aria-label={`Go to slide ${i + 1}`}
              className={`h-1.5 rounded-full transition-all ${i === index ? 'w-6 bg-gold' : 'w-1.5 bg-white/50'}`}
            />
          ))}
        </div>
      </div>

      {/* Quick action overlay cards */}
      <div className="relative bg-white text-slateink">
        <div className="mx-auto max-w-7xl px-4">
          <div className="grid grid-cols-2 lg:grid-cols-4 -mt-8 relative z-10 gap-3 pb-6">
            {quickActions.map(({ key, to, Icon }) => (
              <Link
                key={key}
                to={to}
                className="bg-white rounded-xl shadow-gov border border-slate-200 p-4 flex items-center gap-3 hover:border-maroon hover:shadow-lg transition-all"
              >
                <span className="inline-flex items-center justify-center w-10 h-10 rounded-full bg-maroon-50 text-maroon-700 shrink-0">
                  <Icon className="w-5 h-5" strokeWidth={2} />
                </span>
                <span className="font-semibold text-sm leading-tight">{actions[key]}</span>
              </Link>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
