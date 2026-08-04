import { Link } from 'react-router-dom'
import { DEPARTMENTS } from '../../mock/departmentData'
import { useLanguage } from '../../i18n/LanguageContext'

export default function Footer() {
  const { t } = useLanguage()

  return (
    <footer className="mt-16 bg-slateink text-slate-300">
      <img src="/images/banner_strip_riverside.svg" alt="" className="w-full h-1.5 object-cover" />

      <div className="mx-auto max-w-7xl px-4 py-10 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8 text-sm">
        <div>
          <p className="text-white font-bold mb-2">{t('footer.orgName')}</p>
          <p className="text-slate-400 leading-relaxed">{t('footer.disclaimer')}</p>
        </div>

        <div>
          <p className="text-white font-semibold mb-2">{t('footer.departmentsHeading')}</p>
          <ul className="space-y-1.5">
            {DEPARTMENTS.map((dept) => (
              <li key={dept.id}>
                <Link to={dept.route} className="hover:text-gold transition-colors">
                  {dept.shortName}
                </Link>
              </li>
            ))}
          </ul>
        </div>

        <div>
          <p className="text-white font-semibold mb-2">{t('footer.legalHeading')}</p>
          <ul className="space-y-1.5">
            <li>
              <a href="#privacy" className="hover:text-gold transition-colors">
                {t('footer.privacy')}
              </a>
            </li>
            <li>
              <a href="#terms" className="hover:text-gold transition-colors">
                {t('footer.terms')}
              </a>
            </li>
            <li>
              <a href="#accessibility" className="hover:text-gold transition-colors">
                {t('footer.accessibility')}
              </a>
            </li>
          </ul>
        </div>

        <div>
          <p className="text-white font-semibold mb-2">{t('footer.emergencyHeading')}</p>
          <ul className="space-y-1.5">
            <li>{t('footer.infoCenter')}: <span className="text-gold font-semibold">311</span></li>
            <li>{t('footer.police')}: <span className="text-gold font-semibold">119</span></li>
            <li>{t('footer.ambulance')}: <span className="text-gold font-semibold">110</span></li>
            <li>{t('footer.disaster')}: <span className="text-gold font-semibold">117</span></li>
          </ul>
        </div>
      </div>

      <div className="border-t border-slate-700">
        <div className="mx-auto max-w-7xl px-4 py-4 text-xs text-slate-500 flex flex-col sm:flex-row justify-between gap-2">
          <p>&copy; {new Date().getFullYear()} {t('footer.copyright')}</p>
          <p>{t('footer.builtWith')}</p>
        </div>
      </div>
    </footer>
  )
}
