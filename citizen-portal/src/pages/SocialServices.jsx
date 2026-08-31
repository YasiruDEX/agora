import { useSearchParams } from 'react-router-dom'
import { ShieldAlert } from 'lucide-react'
import ChatWidget from '../components/chat/ChatWidget'
import { getDepartmentById } from '../mock/departmentData'
import { useLanguage } from '../i18n/LanguageContext'

// Matches the two caseworkers seeded in the Case Management MCP Server (see
// mcp-servers/case-management-mcp-server/seed/cases.json) — on-behalf-of identity drives
// which cases each one can see, not the agent's own credentials. In real mode, `id` is sent
// verbatim as the X-OBO-Token header, so it must match a token the MCP server recognizes.
const PERSONAS = [
  { id: 'joan.ellis', label: 'Joan Ellis', hint: 'Assigned: CASE-1001, CASE-1002, CASE-1003' },
  { id: 'renee.alvarez', label: 'Renee Alvarez', hint: 'Assigned: CASE-1004, CASE-1005, CASE-1006' },
]

export default function SocialServices() {
  const dept = getDepartmentById('social-services')
  const { t } = useLanguage()
  const [params, setParams] = useSearchParams()
  const view = params.get('view') === 'caseworker' ? 'caseworker' : 'citizen'
  const persona = params.get('persona') === 'renee.alvarez' ? 'renee.alvarez' : 'joan.ellis'

  function setView(next) {
    const p = new URLSearchParams(params)
    p.set('view', next)
    setParams(p, { replace: true })
  }

  function setPersona(next) {
    const p = new URLSearchParams(params)
    p.set('persona', next)
    setParams(p, { replace: true })
  }

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex items-center gap-3 mb-2">
        <img src={dept.seal} alt="" className="w-10 h-10" />
        <h1 className="text-2xl font-bold text-slateink">{t('pages.socialServices.title')}</h1>
      </div>
      <p className="text-slate-600 mb-6">{t('pages.socialServices.description')}</p>

      {/* View toggle */}
      <div className="inline-flex rounded-full border border-slate-300 bg-white p-1 mb-6">
        <button
          onClick={() => setView('citizen')}
          className={`px-4 py-1.5 rounded-full text-sm font-semibold transition-colors ${
            view === 'citizen' ? 'bg-brand text-white' : 'text-slateink hover:bg-surface'
          }`}
        >
          {t('social.citizenTab')}
        </button>
        <button
          onClick={() => setView('caseworker')}
          className={`px-4 py-1.5 rounded-full text-sm font-semibold transition-colors ${
            view === 'caseworker' ? 'bg-brand text-white' : 'text-slateink hover:bg-surface'
          }`}
        >
          {t('social.caseworkerTab')}
        </button>
      </div>

      {view === 'citizen' ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-1 space-y-3">
            {dept.services.map((svc) => (
              <div key={svc.id} className="bg-white rounded-lg border border-slate-200 p-3">
                <p className="font-semibold text-sm">{t(`services.${svc.id}.title`)}</p>
                <p className="text-xs text-slate-500">{t(`services.${svc.id}.description`)}</p>
              </div>
            ))}
          </div>
          <div className="lg:col-span-2">
            <ChatWidget agentKey="citizen-inquiry-social-services" mode="embedded" seal={dept.seal} />
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-1 space-y-4">
            <div className="rounded-lg border-l-4 border-brand bg-brand-50 text-brand-700 p-3.5 text-sm flex gap-3">
              <ShieldAlert className="w-5 h-5 shrink-0 mt-0.5" strokeWidth={2} />
              <div>
                <p className="font-semibold">{t('social.oboTitle')}</p>
                <p className="mt-0.5 opacity-90">{t('social.oboText')}</p>
              </div>
            </div>
            <div className="bg-white rounded-lg border border-slate-200 p-4">
              <p className="text-sm font-semibold text-brand mb-2">{t('social.activeCaseworker')}</p>
              <div className="space-y-2">
                {PERSONAS.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => setPersona(p.id)}
                    className={`w-full text-left px-3 py-2 rounded-lg border transition-colors ${
                      persona === p.id ? 'border-brand bg-brand-50' : 'border-slate-200 hover:bg-surface'
                    }`}
                  >
                    <p className="font-semibold text-sm">{p.label}</p>
                    <p className="text-xs text-slate-500">{p.hint}</p>
                  </button>
                ))}
              </div>
            </div>
            <p className="text-xs text-slate-500">{t('social.tryAsJoan')}</p>
          </div>
          <div className="lg:col-span-2">
            <ChatWidget key={persona} agentKey="case-management" mode="embedded" userId={persona} seal={dept.seal} />
          </div>
        </div>
      )}
    </div>
  )
}
