import ChatWidget from '../components/chat/ChatWidget'
import { getDepartmentById } from '../mock/departmentData'
import { useLanguage } from '../i18n/LanguageContext'

export default function ContactCenter() {
  const dept = getDepartmentById('contact-center')
  const { t } = useLanguage()

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8 grid grid-cols-1 lg:grid-cols-3 gap-8">
      <div className="lg:col-span-1">
        <div className="flex items-center gap-3 mb-2">
          <img src={dept.seal} alt="" className="w-10 h-10" />
          <h1 className="text-2xl font-bold text-slateink">{t('pages.contactCenter.title')}</h1>
        </div>
        <p className="text-slate-600 mb-4">{t('pages.contactCenter.description')}</p>
        <div className="bg-white rounded-lg border border-slate-200 p-4 mb-4">
          <p className="text-sm font-semibold text-brand mb-2">{t('contact.hotlineLabel')}</p>
          <a href={`tel:${dept.hotline}`} className="text-2xl font-extrabold text-slateink">
            {dept.hotline}
          </a>
        </div>
        <ul className="space-y-2">
          {dept.services.map((svc) => (
            <li key={svc.id} className="bg-white rounded-lg border border-slate-200 p-3">
              <p className="font-semibold text-sm">{t(`services.${svc.id}.title`)}</p>
              <p className="text-xs text-slate-500">{t(`services.${svc.id}.description`)}</p>
            </li>
          ))}
        </ul>
      </div>

      <div className="lg:col-span-2">
        <ChatWidget agentKey="citizen-inquiry" mode="embedded" seal={dept.seal} />
      </div>
    </div>
  )
}
