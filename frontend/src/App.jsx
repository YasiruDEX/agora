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

// The floating assistant is always functionally the Citizen Inquiry Agent
// (agentKey="citizen-inquiry"), but re-brands its displayed name/department
// per department route — a "Welfare & Eligibility Assistant" persona on
// /social-services, a "Tax & Revenue Rate Assistant" persona on /tax-revenue,
// etc. — per the department-specific agent rebranding requirement.
const ROUTE_BRANDING = {
  '/': 'citizenInquiry',
  '/contact-center': 'citizenInquiry',
  '/social-services': 'welfareEligibility',
  '/permits': 'planningPermits',
  '/tax-revenue': 'taxRevenueAssistant',
  '/records': 'recordsFoiaBrand',
}

function FloatingAssistant() {
  const location = useLocation()
  const brandI18nKey = ROUTE_BRANDING[location.pathname] || 'citizenInquiry'
  // Remount on route change so the greeting/session refreshes for the new persona.
  return <ChatWidget key={brandI18nKey} agentKey="citizen-inquiry" mode="floating" brandI18nKey={brandI18nKey} />
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
