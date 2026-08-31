import { Routes, Route, useLocation } from 'react-router-dom'
import { LanguageProvider } from './i18n/LanguageContext'
import Header from './components/layout/Header'
import TickerBanner from './components/layout/TickerBanner'
import Navigation from './components/layout/Navigation'
import Footer from './components/layout/Footer'
import ChatWidget from './components/chat/ChatWidget'
import Home from './pages/Home'
import ContactCenter from './pages/ContactCenter'
import SocialServices from './pages/SocialServices'
import PermitsLicensing from './pages/PermitsLicensing'
import TaxRevenue from './pages/TaxRevenue'
import RecordsCompliance from './pages/RecordsCompliance'

// The floating assistant is always the Citizen Inquiry Agent kind, but which *instance* it
// talks to — and its displayed persona name — both switch per department route, matching
// PLAN.md §6: same agent kind, one deployed instance (and namespace) per department.
const ROUTE_AGENT = {
  '/': { agentKey: 'citizen-inquiry-contact-center', brandI18nKey: 'citizenInquiry' },
  '/contact-center': { agentKey: 'citizen-inquiry-contact-center', brandI18nKey: 'citizenInquiry' },
  '/social-services': { agentKey: 'citizen-inquiry-social-services', brandI18nKey: 'welfareEligibility' },
  '/permits': { agentKey: 'citizen-inquiry-permits-licensing', brandI18nKey: 'planningPermits' },
  '/tax-revenue': { agentKey: 'citizen-inquiry-tax-revenue', brandI18nKey: 'taxRevenueAssistant' },
  '/records': { agentKey: 'citizen-inquiry-records-compliance', brandI18nKey: 'recordsFoiaBrand' },
}

function FloatingAssistant() {
  const location = useLocation()
  const { agentKey, brandI18nKey } = ROUTE_AGENT[location.pathname] || ROUTE_AGENT['/']
  // Remount on route change so the greeting/session refreshes for the new instance/persona.
  return <ChatWidget key={agentKey} agentKey={agentKey} mode="floating" brandI18nKey={brandI18nKey} />
}

export default function App() {
  return (
    <LanguageProvider>
      <div className="min-h-screen flex flex-col bg-surface">
        <TickerBanner />
        <Header />
        <Navigation />

        <main className="flex-1">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/contact-center" element={<ContactCenter />} />
            <Route path="/social-services" element={<SocialServices />} />
            <Route path="/permits" element={<PermitsLicensing />} />
            <Route path="/tax-revenue" element={<TaxRevenue />} />
            <Route path="/records" element={<RecordsCompliance />} />
          </Routes>
        </main>

        <Footer />

        {/* Global floating assistant, available on every page */}
        <FloatingAssistant />
      </div>
    </LanguageProvider>
  )
}
