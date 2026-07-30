import { Routes, Route } from 'react-router-dom'
import Header from './components/layout/Header'
import Navigation from './components/layout/Navigation'
import Footer from './components/layout/Footer'
import ChatWidget from './components/chat/ChatWidget'
import Home from './pages/Home'
import ContactCenter from './pages/ContactCenter'
import SocialServices from './pages/SocialServices'
import PermitsLicensing from './pages/PermitsLicensing'
import TaxRevenue from './pages/TaxRevenue'
import RecordsCompliance from './pages/RecordsCompliance'

export default function App() {
  return (
    <div className="min-h-screen flex flex-col bg-surface">
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
      <ChatWidget agentKey="citizen-inquiry" mode="floating" />
    </div>
  )
}
