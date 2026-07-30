import { useSearchParams } from 'react-router-dom'
import { ShieldAlert } from 'lucide-react'
import ChatWidget from '../components/chat/ChatWidget'
import { getDepartmentById } from '../mock/departmentData'

const PERSONAS = [
  { id: 'joan.ellis', label: 'Joan Ellis', hint: 'Assigned: CASE-2026-001 (Sunethra Dias)' },
  { id: 'marcus.lee', label: 'Marcus Lee', hint: 'Assigned: CASE-2026-002 (Nimal Silva)' },
]

export default function SocialServices() {
  const dept = getDepartmentById('social-services')
  const [params, setParams] = useSearchParams()
  const view = params.get('view') === 'caseworker' ? 'caseworker' : 'citizen'
  const persona = params.get('persona') === 'marcus.lee' ? 'marcus.lee' : 'joan.ellis'

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
    <div className="mx-auto max-w-7xl px-4 py-8">
      <h1 className="text-2xl font-bold text-slateink mb-2">{dept.name}</h1>
      <p className="text-slate-600 mb-6">{dept.description}</p>

      {/* View toggle */}
      <div className="inline-flex rounded-full border border-slate-300 bg-white p-1 mb-6">
        <button
          onClick={() => setView('citizen')}
          className={`px-4 py-1.5 rounded-full text-sm font-semibold transition-colors ${
            view === 'citizen' ? 'bg-maroon text-white' : 'text-slateink hover:bg-surface'
          }`}
        >
          Citizen Services
        </button>
        <button
          onClick={() => setView('caseworker')}
          className={`px-4 py-1.5 rounded-full text-sm font-semibold transition-colors ${
            view === 'caseworker' ? 'bg-maroon text-white' : 'text-slateink hover:bg-surface'
          }`}
        >
          Caseworker Portal
        </button>
      </div>

      {view === 'citizen' ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-1 space-y-3">
            {dept.services.map((svc) => (
              <div key={svc.id} className="bg-white rounded-lg border border-slate-200 p-3">
                <p className="font-semibold text-sm">{svc.title}</p>
                <p className="text-xs text-slate-500">{svc.description}</p>
              </div>
            ))}
          </div>
          <div className="lg:col-span-2">
            <ChatWidget agentKey="benefits-eligibility" mode="embedded" />
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-1 space-y-4">
            <div className="rounded-lg border-l-4 border-maroon bg-maroon-50 text-maroon-700 p-3.5 text-sm flex gap-3">
              <ShieldAlert className="w-5 h-5 shrink-0 mt-0.5" strokeWidth={2} />
              <div>
                <p className="font-semibold">On-Behalf-Of (OBO) Access Control</p>
                <p className="mt-0.5 opacity-90">
                  This agent only shows cases assigned to the active caseworker. Switch personas below to see the
                  security notice in action.
                </p>
              </div>
            </div>
            <div className="bg-white rounded-lg border border-slate-200 p-4">
              <p className="text-sm font-semibold text-maroon mb-2">Active Caseworker</p>
              <div className="space-y-2">
                {PERSONAS.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => setPersona(p.id)}
                    className={`w-full text-left px-3 py-2 rounded-lg border transition-colors ${
                      persona === p.id ? 'border-maroon bg-maroon-50' : 'border-slate-200 hover:bg-surface'
                    }`}
                  >
                    <p className="font-semibold text-sm">{p.label}</p>
                    <p className="text-xs text-slate-500">{p.hint}</p>
                  </button>
                ))}
              </div>
            </div>
            <p className="text-xs text-slate-500">
              Try asking as Joan Ellis: <em>"Summarize case CASE-2026-002"</em> — assigned to Marcus Lee — to see the
              access-denied security notice.
            </p>
          </div>
          <div className="lg:col-span-2">
            <ChatWidget key={persona} agentKey="case-management" mode="embedded" userId={persona} />
          </div>
        </div>
      )}
    </div>
  )
}
