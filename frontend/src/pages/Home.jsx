import { Phone, HeartHandshake, Building2, Landmark, FileText } from 'lucide-react'
import HeroCarousel from '../components/common/HeroCarousel'
import ServiceGrid from '../components/common/ServiceGrid'
import GazetteNoticeCard from '../components/common/GazetteNoticeCard'
import ServiceCard from '../components/common/ServiceCard'
import ChatWidget from '../components/chat/ChatWidget'
import { DEPARTMENTS } from '../mock/departmentData'
import { useLanguage } from '../i18n/LanguageContext'

const DEPT_ICONS = {
  'contact-center': Phone,
  'social-services': HeartHandshake,
  permits: Building2,
  'tax-revenue': Landmark,
  records: FileText,
}

const PAGE_KEY_BY_DEPT = {
  'contact-center': 'contactCenter',
  'social-services': 'socialServices',
  permits: 'permits',
  'tax-revenue': 'taxRevenue',
  records: 'records',
}

export default function Home() {
  const { t } = useLanguage()
  const gazetteItems = t('gazette.items')

  return (
    <div>
      <HeroCarousel />

      <div className="mx-auto max-w-7xl px-4 py-10 space-y-10">
        <ServiceGrid />

        {/* Department directory */}
        <section>
          <div className="flex items-baseline justify-between mb-4">
            <h2 className="text-xl font-bold text-slateink">{t('pages.home.deptDirectory')}</h2>
            <span className="text-xs text-slate-500">{t('pages.home.deptDirectorySub')}</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {DEPARTMENTS.map((dept) => (
              <ServiceCard
                key={dept.id}
                to={dept.route}
                title={t(`pages.${PAGE_KEY_BY_DEPT[dept.id]}.title`)}
                description={t(`pages.${PAGE_KEY_BY_DEPT[dept.id]}.description`)}
                color={dept.color}
                Icon={DEPT_ICONS[dept.id]}
              />
            ))}
          </div>
        </section>

        {/* Gazette notices */}
        <section>
          <div className="flex items-baseline justify-between mb-4">
            <h2 className="text-xl font-bold text-slateink">{t('gazette.title')}</h2>
            <span className="text-xs text-slate-500 cursor-default">{t('gazette.viewAll')}</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {gazetteItems.map((item, i) => (
              <GazetteNoticeCard key={i} tag={item.tag} title={item.title} date={item.date} />
            ))}
          </div>
        </section>

        {/* Central inquiry agent, embedded */}
        <section>
          <div className="flex items-baseline justify-between mb-4">
            <h2 className="text-xl font-bold text-slateink">{t('pages.home.askInquiry')}</h2>
            <span className="text-xs text-slate-500">{t('pages.home.askInquirySub')}</span>
          </div>
          <div className="max-w-2xl">
            <ChatWidget agentKey="citizen-inquiry" mode="embedded" seal="/images/department_seals/contact_center_seal.svg" />
          </div>
        </section>
      </div>
    </div>
  )
}
