import { useSearchParams } from 'react-router-dom'
import ChatWidget from '../components/chat/ChatWidget'
import { getDepartmentById } from '../mock/departmentData'
import { useLanguage } from '../i18n/LanguageContext'

export default function PermitsLicensing() {
  const dept = getDepartmentById('permits')
  const { t } = useLanguage()
  const [params, setParams] = useSearchParams()
  const division = params.get('div') === 'business' ? 'business' : 'building'

  function setDivision(next) {
    const p = new URLSearchParams(params)
    p.set('div', next)
    setParams(p, { replace: true })
  }

  const activeDivision = dept.divisions.find((d) => d.id === division)

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <div className="flex items-center gap-3 mb-2">
        <img src={dept.seal} alt="" className="w-10 h-10" />
        <h1 className="text-2xl font-bold text-slateink">{t('pages.permits.title')}</h1>
      </div>
      <p className="text-slate-600 mb-6">{t('pages.permits.description')}</p>

      <div className="inline-flex rounded-full border border-slate-300 bg-white p-1 mb-6">
        {dept.divisions.map((d) => (
          <button
            key={d.id}
            onClick={() => setDivision(d.id)}
            className={`px-4 py-1.5 rounded-full text-sm font-semibold transition-colors ${
              division === d.id ? 'bg-maroon text-white' : 'text-slateink hover:bg-surface'
            }`}
          >
            {d.label}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-1 space-y-3">
          <p className="text-xs uppercase tracking-wide text-slate-500 font-semibold">{t('permits.servicesInDivision')}</p>
          {dept.services
            .filter((svc) => (division === 'building' ? svc.id !== 'trade-license' : svc.id === 'trade-license'))
            .map((svc) => (
              <div key={svc.id} className="bg-white rounded-lg border border-slate-200 p-3">
                <p className="font-semibold text-sm">{t(`services.${svc.id}.title`)}</p>
                <p className="text-xs text-slate-500">{t(`services.${svc.id}.description`)}</p>
              </div>
            ))}
          <div className="bg-white rounded-lg border border-slate-200 p-3 text-xs text-slate-500">{t('permits.isolationNote')}</div>
        </div>
        <div className="lg:col-span-2">
          <ChatWidget key={division} agentKey={activeDivision.agentKey} mode="embedded" context={{ division }} seal={dept.seal} />
        </div>
      </div>
    </div>
  )
}
