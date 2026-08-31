/**
 * Static metadata for departments and their agent instances. Drives the
 * navigation links, home page directory, and department page headers/badges.
 * `services` is descriptive text shown on each department page (what the
 * agent can help with) — not links to separate pages.
 *
 * Agent catalog matches PLAN.md §5 exactly — 3 agent kinds, 8 running instances:
 *   - Citizen Inquiry Agent  — one instance per department (5): Social Services,
 *     Permits & Licensing, Tax & Revenue, Records & Compliance, Contact Center.
 *   - Case Management Agent  — 1 instance, Social Services only (caseworker view).
 *   - Permit & Licensing Agent — 2 instances, both under Permits & Licensing:
 *     Building Permits and Business & Trade Licenses.
 */

export const LLM_TIERS = {
  CLOUD: { key: 'cloud', label: 'Cloud OK', className: 'bg-emerald-100 text-emerald-800 border-emerald-300' },
  ONPREM: {
    key: 'onprem',
    label: 'On-Prem · PII Restricted',
    className: 'bg-brand-50 text-brand-700 border-brand-300',
  },
}

export const AGENTS = {
  // --- Citizen Inquiry Agent — same agent kind, 5 department instances ---
  'citizen-inquiry-contact-center': {
    key: 'citizen-inquiry-contact-center',
    i18nKey: 'citizenInquiry',
    name: 'Citizen Inquiry Agent',
    department: 'Contact Center',
    tier: LLM_TIERS.CLOUD,
    quickReplies: [
      'What are the opening hours for the Municipal Office?',
      'Where do I pay my assessment rates?',
      'How do I request a birth certificate extract?',
    ],
  },
  'citizen-inquiry-social-services': {
    key: 'citizen-inquiry-social-services',
    i18nKey: 'benefitsEligibility',
    name: 'Citizen Inquiry Agent',
    department: 'Riverside County Department of Social Services',
    tier: LLM_TIERS.CLOUD,
    quickReplies: [
      'How much do I need to qualify for CalFresh with a household of 4?',
      'What documents do I need for Medi-Cal?',
      'What is the CalWORKs Welfare-to-Work requirement?',
    ],
  },
  'citizen-inquiry-permits-licensing': {
    key: 'citizen-inquiry-permits-licensing',
    i18nKey: 'citizenInquiryPermits',
    name: 'Citizen Inquiry Agent',
    department: 'Riverside County Permits & Licensing',
    tier: LLM_TIERS.CLOUD,
    quickReplies: [
      'What permits do I need for an ADU?',
      'What are the office hours for Building & Safety?',
      'How long does a plan check take?',
    ],
  },
  'citizen-inquiry-tax-revenue': {
    key: 'citizen-inquiry-tax-revenue',
    i18nKey: 'taxAssistance',
    name: 'Citizen Inquiry Agent',
    department: 'Riverside County Tax & Revenue',
    tier: LLM_TIERS.CLOUD,
    quickReplies: ['Check my rates balance', 'Pay Q1 assessment rates for PROP-RVC-2026-88', 'What are the trade tax tiers?'],
  },
  'citizen-inquiry-records-compliance': {
    key: 'citizen-inquiry-records-compliance',
    i18nKey: 'recordsFoia',
    name: 'Citizen Inquiry Agent',
    department: 'Riverside County Records & Compliance',
    tier: LLM_TIERS.CLOUD,
    quickReplies: ['Retrieve public record REC-2026-101', 'Retrieve public record REC-2026-102', 'Submit a FOIA request'],
  },

  // --- Case Management Agent — 1 instance, Social Services only ---
  'case-management': {
    key: 'case-management',
    i18nKey: 'caseManagement',
    name: 'Case Management Agent',
    department: 'Riverside County Department of Social Services (Caseworker)',
    tier: LLM_TIERS.ONPREM,
    quickReplies: ['List my current cases', 'Summarize case CASE-1001', 'Add a note to case CASE-1003'],
  },

  // --- Permit & Licensing Agent — 2 instances, both under Permits & Licensing ---
  'permit-licensing-building': {
    key: 'permit-licensing-building',
    i18nKey: 'permitsBuilding',
    name: 'Permit & Licensing Agent — Building Permits',
    department: 'Riverside County Permits & Licensing',
    tier: LLM_TIERS.CLOUD,
    quickReplies: ['Check status for permit BP-2026-00042', 'What would an ADU permit cost for a $90,000 project?'],
  },
  'permit-licensing-business': {
    key: 'permit-licensing-business',
    i18nKey: 'permitsBusiness',
    name: 'Permit & Licensing Agent — Business & Trade Licenses',
    department: 'Riverside County Permits & Licensing',
    tier: LLM_TIERS.CLOUD,
    quickReplies: ['Check status for business license BL-2026-00012', 'What is the annual fee for a business license?'],
  },
}

export const DEPARTMENTS = [
  {
    id: 'contact-center',
    name: 'Contact Center',
    shortName: 'Contact Center',
    route: '/contact-center',
    color: 'brand',
    description: 'General inquiries, service directory, and SLA information for all departments.',
    hotline: '311',
    seal: '/images/department_seals/contact_center_seal.svg',
    agentKey: 'citizen-inquiry-contact-center',
    services: [
      { id: 'general-faq', title: 'General FAQs', description: 'Common questions about municipal services.' },
      { id: 'service-directory', title: 'Service Directory', description: 'Find the right department for your need.' },
      { id: 'sla-lookup', title: 'SLA Enquiries', description: 'Check standard processing timelines.' },
    ],
  },
  {
    id: 'social-services',
    name: 'Riverside County Department of Social Services',
    shortName: 'Social Services',
    route: '/social-services',
    color: 'govgreen',
    description: 'CalFresh, CalWORKs, Medi-Cal, IHSS, General Relief, and caseworker case management.',
    hotline: '311',
    seal: '/images/department_seals/social_services_seal.svg',
    agentKey: 'citizen-inquiry-social-services',
    caseworkerAgentKey: 'case-management',
    services: [
      { id: 'senior-allowance', title: 'IHSS (In-Home Supportive Services)', description: 'In-home caregiving support for aged, blind, or disabled residents.' },
      { id: 'medical-aid', title: 'Medi-Cal', description: 'Free or low-cost health coverage.' },
      { id: 'public-assistance', title: 'CalFresh / CalWORKs / General Relief', description: 'Food benefits, cash aid, and Welfare-to-Work.' },
    ],
  },
  {
    id: 'permits',
    name: 'Riverside County Permits & Licensing',
    shortName: 'Permits & Licensing',
    route: '/permits',
    color: 'gold',
    description: 'Building permit approvals, fee estimates, and business/trade licenses.',
    hotline: '311',
    seal: '/images/department_seals/permits_seal.svg',
    agentKey: 'citizen-inquiry-permits-licensing',
    divisions: [
      { id: 'building', label: 'Building Permits Division', agentKey: 'permit-licensing-building' },
      { id: 'business', label: 'Business & Trade Licenses Division', agentKey: 'permit-licensing-business' },
    ],
    services: [
      { id: 'building-plan', title: 'Building Permit Approval', description: 'Submit and track building/ADU/solar/pool permit applications.' },
      { id: 'street-line', title: 'Fee Schedule Lookup', description: 'Estimate fees for any permit type.' },
      { id: 'trade-license', title: 'Business License', description: 'Register and renew a business license.' },
    ],
  },
  {
    id: 'tax-revenue',
    name: 'Riverside County Tax & Revenue',
    shortName: 'Tax & Revenue',
    route: '/tax-revenue',
    color: 'brand',
    description: 'Property assessment rates, trade tax tiers, and online rate payments.',
    hotline: '311',
    seal: '/images/department_seals/tax_revenue_seal.svg',
    agentKey: 'citizen-inquiry-tax-revenue',
    services: [
      { id: 'assessment-rates', title: 'Assessment Rates Payment', description: 'Pay quarterly property assessment rates online.' },
      { id: 'non-arrears', title: 'Non-Arrears Certificate', description: 'Confirm your property has no outstanding balance.' },
      { id: 'trade-tax', title: 'Trade Tax Collection', description: 'Business trade tax tiers and payment.' },
    ],
  },
  {
    id: 'records',
    name: 'Riverside County Records & Compliance',
    shortName: 'Records & Compliance',
    route: '/records',
    color: 'govgreen',
    description: 'Public records (CPRA) requests, vital records, and civil registration extracts.',
    hotline: '311',
    seal: '/images/department_seals/records_seal.svg',
    agentKey: 'citizen-inquiry-records-compliance',
    services: [
      { id: 'foia-request', title: 'Public Records Request', description: 'Submit a California Public Records Act (CPRA) request.' },
      { id: 'birth-death-marriage', title: 'Birth / Death / Marriage Extracts', description: 'Request certified civil registration extracts.' },
      { id: 'grievance', title: 'Public Complaints & Grievances', description: 'Lodge a formal complaint with the county.' },
    ],
  },
]

export function getDepartmentById(id) {
  return DEPARTMENTS.find((d) => d.id === id)
}

export function getAgent(agentKey) {
  return AGENTS[agentKey]
}
