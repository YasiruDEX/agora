import { Link } from 'react-router-dom'
import { DEPARTMENTS } from '../../mock/departmentData'

export default function Footer() {
  return (
    <footer className="mt-16 bg-slateink text-slate-300">
      <img src="/images/flag_strip.svg" alt="" className="w-full h-1.5 object-cover" />

      <div className="mx-auto max-w-7xl px-4 py-10 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8 text-sm">
        <div>
          <p className="text-white font-bold mb-2">Government of Sri Lanka</p>
          <p className="text-slate-400 leading-relaxed">
            This is a demonstration portal built to showcase multi-agent citizen services. It is not the official
            gov.lk website.
          </p>
        </div>

        <div>
          <p className="text-white font-semibold mb-2">Departments</p>
          <ul className="space-y-1.5">
            {DEPARTMENTS.map((dept) => (
              <li key={dept.id}>
                <Link to={dept.route} className="hover:text-gold transition-colors">
                  {dept.shortName}
                </Link>
              </li>
            ))}
          </ul>
        </div>

        <div>
          <p className="text-white font-semibold mb-2">Legal</p>
          <ul className="space-y-1.5">
            <li>
              <a href="#privacy" className="hover:text-gold transition-colors">
                Privacy Policy
              </a>
            </li>
            <li>
              <a href="#terms" className="hover:text-gold transition-colors">
                Terms of Use
              </a>
            </li>
            <li>
              <a href="#accessibility" className="hover:text-gold transition-colors">
                Accessibility Statement
              </a>
            </li>
          </ul>
        </div>

        <div>
          <p className="text-white font-semibold mb-2">Emergency Contacts</p>
          <ul className="space-y-1.5">
            <li>Government Info Center: <span className="text-gold font-semibold">1919</span></li>
            <li>Police Emergency: <span className="text-gold font-semibold">119</span></li>
            <li>Ambulance / Fire: <span className="text-gold font-semibold">110</span></li>
            <li>Disaster Management: <span className="text-gold font-semibold">117</span></li>
          </ul>
        </div>
      </div>

      <div className="border-t border-slate-700">
        <div className="mx-auto max-w-7xl px-4 py-4 text-xs text-slate-500 flex flex-col sm:flex-row justify-between gap-2">
          <p>&copy; {new Date().getFullYear()} Government of Sri Lanka. All rights reserved. (Demo build)</p>
          <p>Built to demonstrate WSO2 Agent Manager multi-department agent instances.</p>
        </div>
      </div>
    </footer>
  )
}
