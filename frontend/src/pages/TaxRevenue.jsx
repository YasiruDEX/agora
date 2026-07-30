import { Info } from 'lucide-react'
import ChatWidget from '../components/chat/ChatWidget'
import { getDepartmentById } from '../mock/departmentData'

export default function TaxRevenue() {
  const dept = getDepartmentById('tax-revenue')

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <h1 className="text-2xl font-bold text-slateink mb-2">{dept.name}</h1>
      <p className="text-slate-600 mb-6">{dept.description}</p>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-1 space-y-3">
          <div className="rounded-lg border-l-4 border-gold-500 bg-gold-50 text-gold-900 p-3.5 text-sm flex gap-3">
            <Info className="w-5 h-5 shrink-0 mt-0.5" strokeWidth={2} />
            <p>
              Ask: "Pay Q1 assessment rates for PROP-COL-2026-88" to see the prompt-payment discount and online
              checkout flow.
            </p>
          </div>
          {dept.services.map((svc) => (
            <div key={svc.id} className="bg-white rounded-lg border border-slate-200 p-3">
              <p className="font-semibold text-sm">{svc.title}</p>
              <p className="text-xs text-slate-500">{svc.description}</p>
            </div>
          ))}
        </div>
        <div className="lg:col-span-2">
          <ChatWidget agentKey="tax-assistance" mode="embedded" />
        </div>
      </div>
    </div>
  )
}
