/**
 * Static metadata for departments and their agent instances. Drives the
 * navigation links, home page directory, and department page headers/badges.
 * `services` is descriptive text shown on each department page (what the
 * agent can help with) — not links to separate pages.
 */

export const LLM_TIERS = {
  CLOUD: { key: 'cloud', label: 'Cloud OK', className: 'bg-emerald-100 text-emerald-800 border-emerald-300' },
  ONPREM: {
    key: 'onprem',
    label: 'On-Prem · PII Restricted',
    className: 'bg-maroon-50 text-maroon-700 border-maroon-300',
  },
}

export const AGENTS = {
  'citizen-inquiry': {
    key: 'citizen-inquiry',
    name: 'Citizen Inquiry Agent',
    department: 'Contact Center',
    port: 8001,
    tier: LLM_TIERS.CLOUD,
    quickReplies: [
      'What are the opening hours for the Municipal Office?',
      'Where do I pay my assessment rates?',
      'How do I request a birth certificate extract?',
    ],
  },
  'benefits-eligibility': {
    key: 'benefits-eligibility',
    name: 'Benefits Eligibility Agent',
    department: 'Department of Social Services',
    port: 8000,
    tier: LLM_TIERS.CLOUD,
    quickReplies: [
      'Am I eligible for the Senior Citizen Allowance?',
      'What documents do I need for medical low-income aid?',
      'Check my application status',
    ],
  },
  'case-management': {
    key: 'case-management',
    name: 'Case Management Agent',
    department: 'Department of Social Services (Caseworker)',
    port: 8005,
    tier: LLM_TIERS.ONPREM,
    quickReplies: ['Summarize case CASE-2026-001', 'Summarize case CASE-2026-002', 'Draft next steps'],
  },
  'permits-building': {
    key: 'permits-building',
    name: 'Permit & Licensing Agent — Building Permits',
    department: 'Permits & Licensing Department',
    port: 8002,
    tier: LLM_TIERS.CLOUD,
    quickReplies: ['Check status for NIC 198204100V', 'What documents do I need for a Building Plan?'],
  },
  'permits-business': {
    key: 'permits-business',
    name: 'Permit & Licensing Agent — Business & Trade Licenses',
    department: 'Permits & Licensing Department',
    port: 8003,
    tier: LLM_TIERS.CLOUD,
    quickReplies: ['Check status for NIC 199012300V', 'What documents do I need for a Trade License?'],
  },
  'tax-assistance': {
    key: 'tax-assistance',
    name: 'Tax & Assessment Agent',
    department: 'Tax & Revenue Department',
    port: 8004,
    tier: LLM_TIERS.CLOUD,
    quickReplies: ['Check my rates balance', 'Pay Q1 assessment rates for PROP-COL-2026-88', 'What are the trade tax tiers?'],
  },
  'records-foia': {
    key: 'records-foia',
    name: 'Records / FOIA Agent',
    department: 'Department of Records & Compliance',
    port: 8006,
    tier: LLM_TIERS.CLOUD,
    quickReplies: ['Retrieve public record REC-2026-101', 'Retrieve public record REC-2026-102', 'Submit a FOIA request'],
  },
}

export const DEPARTMENTS = [
  {
    id: 'contact-center',
    name: 'Contact Center',
    shortName: 'Contact Center',
    route: '/contact-center',
    color: 'maroon',
    description: 'General inquiries, service directory, and SLA information for all departments.',
    hotline: '1919',
    agentKey: 'citizen-inquiry',
    services: [
      { id: 'general-faq', title: 'General FAQs', description: 'Common questions about municipal services.' },
      { id: 'service-directory', title: 'Service Directory', description: 'Find the right department for your need.' },
      { id: 'sla-lookup', title: 'SLA Enquiries', description: 'Check standard processing timelines.' },
    ],
  },
  {
    id: 'social-services',
    name: 'Department of Social Services',
    shortName: 'Social Services',
    route: '/social-services',
    color: 'govgreen',
    description: 'Welfare benefits, senior citizen allowances, medical aid, and caseworker case management.',
    hotline: '1919',
    agentKey: 'benefits-eligibility',
    caseworkerAgentKey: 'case-management',
    services: [
      { id: 'senior-allowance', title: 'Senior Citizen Allowance', description: 'Monthly allowance for citizens aged 60+.' },
      { id: 'medical-aid', title: 'Medical Low-Income Aid', description: 'Support for medical equipment and treatment costs.' },
      { id: 'public-assistance', title: 'Public Assistance Allowance', description: 'Income-based household support.' },
    ],
  },
  {
    id: 'permits',
    name: 'Permits & Licensing Department',
    shortName: 'Permits & Licensing',
    route: '/permits',
    color: 'gold',
    description: 'Building plan approvals, street line certificates, and trade/business licenses.',
    hotline: '1919',
    divisions: [
      { id: 'building', label: 'Building Permits Division', agentKey: 'permits-building' },
      { id: 'business', label: 'Business & Trade Licenses Division', agentKey: 'permits-business' },
    ],
    services: [
      { id: 'building-plan', title: 'Building Plan Approval', description: 'Submit and track building plan applications.' },
      { id: 'street-line', title: 'Street Line Certificate', description: 'Boundary and road reservation certification.' },
      { id: 'trade-license', title: 'Trade Business License', description: 'Register and renew a trade license.' },
    ],
  },
  {
    id: 'tax-revenue',
    name: 'Tax & Revenue Department',
    shortName: 'Tax & Revenue',
    route: '/tax-revenue',
    color: 'maroon',
    description: 'Property assessment rates, trade tax tiers, and online rate payments.',
    hotline: '1919',
    agentKey: 'tax-assistance',
    services: [
      { id: 'assessment-rates', title: 'Assessment Rates Payment', description: 'Pay quarterly property assessment rates online.' },
      { id: 'non-arrears', title: 'Non-Arrears Certificate', description: 'Confirm your property has no outstanding balance.' },
      { id: 'trade-tax', title: 'Trade Tax Collection', description: 'Business trade tax tiers and payment.' },
    ],
  },
  {
    id: 'records',
    name: 'Department of Records & Compliance',
    shortName: 'Records & Compliance',
    route: '/records',
    color: 'govgreen',
    description: 'Public records (RTI/FOIA) requests, disclosure exemption checks, and civil registration extracts.',
    hotline: '1919',
    agentKey: 'records-foia',
    services: [
      { id: 'foia-request', title: 'Public Records Request', description: 'Submit a Right to Information (RTI) request.' },
      { id: 'birth-death-marriage', title: 'Birth / Death / Marriage Extracts', description: 'Request certified civil registration extracts.' },
      { id: 'grievance', title: 'Public Complaints & Grievances', description: 'Lodge a formal complaint with the council.' },
    ],
  },
]

export function getDepartmentById(id) {
  return DEPARTMENTS.find((d) => d.id === id)
}

export function getAgent(agentKey) {
  return AGENTS[agentKey]
}
