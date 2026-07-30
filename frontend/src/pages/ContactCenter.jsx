import ChatWidget from '../components/chat/ChatWidget'
import { getDepartmentById } from '../mock/departmentData'

export default function ContactCenter() {
  const dept = getDepartmentById('contact-center')

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 grid grid-cols-1 lg:grid-cols-3 gap-8">
      <div className="lg:col-span-1">
        <h1 className="text-2xl font-bold text-slateink mb-2">{dept.name}</h1>
        <p className="text-slate-600 mb-4">{dept.description}</p>
        <div className="bg-white rounded-lg border border-slate-200 p-4 mb-4">
          <p className="text-sm font-semibold text-maroon mb-2">Government Info Hotline</p>
          <a href={`tel:${dept.hotline}`} className="text-2xl font-extrabold text-slateink">
            {dept.hotline}
          </a>
        </div>
        <ul className="space-y-2">
          {dept.services.map((svc) => (
            <li key={svc.id} className="bg-white rounded-lg border border-slate-200 p-3">
              <p className="font-semibold text-sm">{svc.title}</p>
              <p className="text-xs text-slate-500">{svc.description}</p>
            </li>
          ))}
        </ul>
      </div>

      <div className="lg:col-span-2">
        <ChatWidget agentKey="citizen-inquiry" mode="embedded" />
      </div>
    </div>
  )
}
