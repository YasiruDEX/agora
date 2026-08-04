import { ShieldAlert } from 'lucide-react'
import ChatWidget from '../components/chat/ChatWidget'
import { getDepartmentById } from '../mock/departmentData'
import { useLanguage } from '../i18n/LanguageContext'

export default function RecordsCompliance() {
  const dept = getDepartmentById('records')
  const { t } = useLanguage()

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex items-center gap-3 mb-2">
        <img src={dept.seal} alt="" className="w-10 h-10" />
        <h1 className="text-2xl font-bold text-slateink">{t('pages.records.title')}</h1>
      </div>
      <p className="text-slate-600 mb-6">{t('pages.records.description')}</p>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-1 space-y-3">
          <div className="rounded-lg border-l-4 border-brand bg-brand-50 text-brand-700 p-3.5 text-sm flex gap-3">
            <ShieldAlert className="w-5 h-5 shrink-0 mt-0.5" strokeWidth={2} />
            <div>
              <p className="font-semibold">{t('records.rtiTitle')}</p>
              <p className="mt-0.5 opacity-90">{t('records.rtiText')}</p>
            </div>
          </div>
          {dept.services.map((svc) => (
            <div key={svc.id} className="bg-white rounded-lg border border-slate-200 p-3">
              <p className="font-semibold text-sm">{t(`services.${svc.id}.title`)}</p>
              <p className="text-xs text-slate-500">{t(`services.${svc.id}.description`)}</p>
            </div>
          ))}
          <div className="bg-white rounded-lg border border-slate-200 p-3 text-xs text-slate-500">{t('records.tryIt')}</div>
        </div>
        <div className="lg:col-span-2">
          <ChatWidget agentKey="records-foia" mode="embedded" seal={dept.seal} />
        </div>
      </div>
    </div>
  )
}
