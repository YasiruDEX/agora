import { ShieldAlert } from 'lucide-react'
import ChatWidget from '../components/chat/ChatWidget'
import { getDepartmentById } from '../mock/departmentData'

export default function RecordsCompliance() {
  const dept = getDepartmentById('records')

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <h1 className="text-2xl font-bold text-slateink mb-2">{dept.name}</h1>
      <p className="text-slate-600 mb-6">{dept.description}</p>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-1 space-y-3">
          <div className="rounded-lg border-l-4 border-maroon bg-maroon-50 text-maroon-700 p-3.5 text-sm flex gap-3">
            <ShieldAlert className="w-5 h-5 shrink-0 mt-0.5" strokeWidth={2} />
            <div>
              <p className="font-semibold">Right to Information (RTI) Act, No. 12 of 2016</p>
              <p className="mt-0.5 opacity-90">
                Some records are exempt from disclosure (e.g. active investigations). Disclosable records
                automatically have PII redacted before release.
              </p>
            </div>
          </div>
          {dept.services.map((svc) => (
            <div key={svc.id} className="bg-white rounded-lg border border-slate-200 p-3">
              <p className="font-semibold text-sm">{svc.title}</p>
              <p className="text-xs text-slate-500">{svc.description}</p>
            </div>
          ))}
          <div className="bg-white rounded-lg border border-slate-200 p-3 text-xs text-slate-500">
            Try: <em>"Retrieve public record REC-2026-101"</em> (redacted PII) or{' '}
            <em>"Retrieve public record REC-2026-102"</em> (statutory exemption).
          </div>
        </div>
        <div className="lg:col-span-2">
          <ChatWidget agentKey="records-foia" mode="embedded" />
        </div>
      </div>
    </div>
  )
}
