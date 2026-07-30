import { Link, useLocation } from 'react-router-dom'
import { DEPARTMENTS } from '../../mock/departmentData'

export default function Navigation() {
  const location = useLocation()

  return (
    <nav className="bg-maroon text-white">
      <div className="mx-auto max-w-7xl px-4">
        <ul className="flex flex-wrap items-stretch">
          <li>
            <Link
              to="/"
              className={`inline-flex items-center h-11 px-4 text-sm font-semibold transition-colors ${
                location.pathname === '/' ? 'bg-maroon-700' : 'hover:bg-maroon-600'
              }`}
            >
              Home
            </Link>
          </li>
          {DEPARTMENTS.map((dept) => (
            <li key={dept.id}>
              <Link
                to={dept.route}
                className={`inline-flex items-center h-11 px-4 text-sm font-semibold transition-colors ${
                  location.pathname === dept.route ? 'bg-maroon-700' : 'hover:bg-maroon-600'
                }`}
              >
                {dept.shortName}
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </nav>
  )
}
