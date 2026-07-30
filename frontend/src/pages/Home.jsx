import { Phone, HeartHandshake, Building2, Landmark, FileText } from 'lucide-react'
import ServiceCard from '../components/common/ServiceCard'
import ChatWidget from '../components/chat/ChatWidget'
import { DEPARTMENTS } from '../mock/departmentData'

const DEPT_ICONS = {
  'contact-center': Phone,
  'social-services': HeartHandshake,
  permits: Building2,
  'tax-revenue': Landmark,
  records: FileText,
}

export default function Home() {
  return (
    <div>
      {/* Hero */}
      <section
        className="relative bg-gradient-to-br from-maroon via-maroon-600 to-maroon-800 text-white bg-cover bg-center"
        style={{ backgroundImage: "linear-gradient(rgba(141,27,61,0.86), rgba(74,14,32,0.92)), url('/images/civic_building_banner.svg')" }}
      >
        <div className="mx-auto max-w-7xl px-4 py-14 text-center">
          <p className="uppercase tracking-widest text-gold text-xs font-bold mb-3">
            Democratic Socialist Republic of Sri Lanka
          </p>
          <h1 className="text-3xl sm:text-4xl font-extrabold mb-3">Government Citizen Services Portal</h1>
          <p className="text-white/85 max-w-2xl mx-auto mb-8">
            One place to find municipal services, submit applications, check status, and chat with the department
            assistant best suited to help — this is a demo showcasing multi-agent AI service delivery.
          </p>

          <form className="max-w-xl mx-auto flex" onSubmit={(e) => e.preventDefault()}>
            <input
              type="search"
              placeholder="Search for a service (e.g. building permit, senior allowance, assessment rates)"
              className="flex-1 rounded-l-full px-5 py-3 text-slateink text-sm focus:outline-none focus:ring-2 focus:ring-gold"
            />
            <button type="submit" className="bg-gold hover:bg-gold-500 text-slateink font-bold px-6 rounded-r-full text-sm">
              Search
            </button>
          </form>
        </div>
      </section>

      <div className="mx-auto max-w-7xl px-4 py-10 space-y-10">
        {/* Department directory */}
        <section>
          <div className="flex items-baseline justify-between mb-4">
            <h2 className="text-xl font-bold text-slateink">Department Directory</h2>
            <span className="text-xs text-slate-500">6 Agent Kinds · ~10 running instances</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {DEPARTMENTS.map((dept) => (
              <ServiceCard
                key={dept.id}
                to={dept.route}
                title={dept.name}
                description={dept.description}
                color={dept.color}
                Icon={DEPT_ICONS[dept.id]}
              />
            ))}
          </div>
        </section>

        {/* Central inquiry agent, embedded */}
        <section>
          <div className="flex items-baseline justify-between mb-4">
            <h2 className="text-xl font-bold text-slateink">Ask the Citizen Inquiry Agent</h2>
            <span className="text-xs text-slate-500">Central Contact Center assistant</span>
          </div>
          <div className="max-w-2xl">
            <ChatWidget agentKey="citizen-inquiry" mode="embedded" />
          </div>
        </section>
      </div>
    </div>
  )
}
