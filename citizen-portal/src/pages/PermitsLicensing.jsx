import { useSearchParams } from 'react-router-dom'
import ChatWidget from '../components/chat/ChatWidget'
import { getDepartmentById } from '../mock/departmentData'
import { useLanguage } from '../i18n/LanguageContext'

export default function PermitsLicensing() {
  const dept = getDepartmentById('permits')
  const { t } = useLanguage()
  const [params, setParams] = useSearchParams()

  // General Citizen Inquiry Agent for this department, alongside the two Permit & Licensing
  // Agent divisions (Building Permits, Business & Trade Licenses) — matches PLAN.md §5/§6:
  // every department has a Citizen Inquiry instance in addition to any specialized agent.
  const TABS = [
    { id: 'inquiry', label: t('permits.generalInquiriesTab'), agentKey: dept.agentKey },
    ...dept.divisions.map((d) => ({ id: d.id, label: d.label, agentKey: d.agentKey })),
  ]

  const activeId = TABS.some((tb) => tb.id === params.get('div')) ? params.get('div') : 'inquiry'
  const activeTab = TABS.find((tb) => tb.id === activeId)

  function setActiveId(next) {
    const p = new URLSearchParams(params)
    p.set('div', next)
    setParams(p, { replace: true })
  }

  const visibleServices =
    activeId === 'inquiry'
      ? dept.services
      : dept.services.filter((svc) => (activeId === 'building' ? svc.id !== 'trade-license' : svc.id === 'trade-license'))

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex items-center gap-3 mb-2">
        <img src={dept.seal} alt="" className="w-10 h-10" />
        <h1 className="text-2xl font-bold text-slateink">{t('pages.permits.title')}</h1>
      </div>
      <p className="text-slate-600 mb-6">{t('pages.permits.description')}</p>

      <div className="inline-flex rounded-full border border-slate-300 bg-white p-1 mb-6">
        {TABS.map((tb) => (
          <button
            key={tb.id}
            onClick={() => setActiveId(tb.id)}
            className={`px-4 py-1.5 rounded-full text-sm font-semibold transition-colors ${
              activeId === tb.id ? 'bg-brand text-white' : 'text-slateink hover:bg-surface'
            }`}
          >
            {tb.label}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-1 space-y-3">
          <p className="text-xs uppercase tracking-wide text-slate-500 font-semibold">{t('permits.servicesInDivision')}</p>
          {visibleServices.map((svc) => (
            <div key={svc.id} className="bg-white rounded-lg border border-slate-200 p-3">
              <p className="font-semibold text-sm">{t(`services.${svc.id}.title`)}</p>
              <p className="text-xs text-slate-500">{t(`services.${svc.id}.description`)}</p>
            </div>
          ))}
          {activeId !== 'inquiry' && (
            <div className="bg-white rounded-lg border border-slate-200 p-3 text-xs text-slate-500">{t('permits.isolationNote')}</div>
          )}
        </div>
        <div className="lg:col-span-2">
          <ChatWidget
            key={activeId}
            agentKey={activeTab.agentKey}
            mode="embedded"
            context={activeId === 'inquiry' ? {} : { division: activeId }}
            seal={dept.seal}
          />
        </div>
      </div>
    </div>
  )
}
