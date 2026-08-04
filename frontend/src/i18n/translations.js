/**
 * Central translation dictionary for the portal (English only).
 * Looked up via dot-path keys through LanguageContext's t() — e.g. t('nav.home').
 */

export const LANGUAGES = [{ code: 'en', label: 'English' }]

export const translations = {
  en: {
    common: {
      search: 'Search',
      cancel: 'Cancel',
      confirm: 'Confirm',
      close: 'Close',
      loading: 'Loading...',
      viewAll: 'View all',
      demoNotice: 'Demo',
    },
    header: {
      portalName: 'Riverside County Government',
      portalSub: 'Official Citizen Services Portal (Demo)',
      searchPlaceholder: 'Search for a service, department, or form...',
      hotlineLabel: 'County Info Hotline',
      indexedServices: 'services indexed',
    },
    ticker: {
      label: 'Latest Updates',
      items: [
        'County Register Notice published — County Administration Office circular on service delivery standards',
        'Riverside County Digital Services Initiative 2026 — 40 more county services now available online',
        'Board of Supervisors Decision: Approval granted for expansion of one-stop citizen service centers',
        'Assessment rates for Q1 2026 due 31 March — 5% prompt payment discount applies',
        'Freedom of Information Act (FOIA) processing times updated for all county offices',
      ],
    },
    nav: {
      home: 'Home',
      contactCenter: 'Contact Center',
      socialServices: 'Social Services',
      permits: 'Permits & Licensing',
      taxRevenue: 'Tax & Revenue',
      records: 'Records & Compliance',
      viewServices: 'View services',
    },
    hero: {
      kicker: 'Riverside County',
      searchPlaceholder: 'Search for a service (e.g. building permit, senior allowance, assessment rates)',
      searchButton: 'Search',
      slides: [
        {
          title: 'Government Citizen Services Portal',
          subtitle:
            'One place to find municipal services, submit applications, check status, and chat with the department assistant best suited to help.',
          image: 'secretariat',
        },
        {
          title: 'Riverside County Board of Supervisors',
          subtitle: 'Track legislation, public notices, and Board decisions that shape citizen services countywide.',
          image: 'parliament',
        },
        {
          title: 'Municipal & Treasury Services',
          subtitle: 'Pay assessment rates, renew licenses, and manage property records from a single dashboard.',
          image: 'treasury',
        },
        {
          title: 'One-Stop County Service Offices',
          subtitle: 'Every department, staffed by a dedicated AI assistant and a named human officer, in one portal.',
          image: 'municipal',
        },
      ],
      actions: {
        payRates: 'Pay Property Rates',
        checkBenefits: 'Check Benefit Status',
        trackPermit: 'Track Building Permit',
        requestFoia: 'Request FOIA Records',
      },
    },
    serviceGrid: {
      title: 'Government Service Directory',
      subtitle: '1,400+ indexed government services across 12 categories',
      categories: [
        { id: 'housing', title: 'Housing & Land', description: 'Land permits, deeds, and housing schemes.' },
        { id: 'tax', title: 'Tax & Revenue', description: 'Assessment rates, trade tax, and payments.' },
        { id: 'social', title: 'Social Services', description: 'Welfare allowances and medical aid.' },
        { id: 'permits', title: 'Permits & Licensing', description: 'Building plans and trade licenses.' },
        { id: 'records', title: 'Records & Registration', description: 'Civil registration and public records.' },
        { id: 'health', title: 'Health & Environment', description: 'Sanitation permits and environmental licenses.' },
        { id: 'education', title: 'Education', description: 'School admissions and scholarships.' },
        { id: 'transport', title: 'Transport & Motor Traffic', description: 'Vehicle registration and licensing.' },
        { id: 'employment', title: 'Employment & Labor', description: 'Job registration and labor disputes.' },
        { id: 'justice', title: 'Justice & Legal Affairs', description: 'Court services and legal aid.' },
        { id: 'agriculture', title: 'Agriculture & Irrigation', description: 'Farmer subsidies and irrigation permits.' },
        { id: 'foreign', title: 'Foreign Affairs & Immigration', description: 'Passports and visa services.' },
      ],
    },
    gazette: {
      title: 'Public Notices & Announcements',
      viewAll: 'View all notices',
      items: [
        { tag: 'NOTICE', title: 'County Register No. 2426/18 — Assessment Rate Revision 2026', date: '2026-07-24' },
        { tag: 'ADVISORY', title: 'County Administrative Advisory 05/2026 — Digital Service Delivery Standards', date: '2026-07-20' },
        { tag: 'BOARD', title: 'Board of Supervisors Decision — Expansion of One-Stop Citizen Service Centers', date: '2026-07-15' },
        { tag: 'ALERT', title: 'Service Alert — Revised Office Hours for County Service Offices', date: '2026-07-10' },
      ],
    },
    footer: {
      orgName: 'Riverside County Government',
      disclaimer:
        'This is a demonstration portal built to showcase multi-agent citizen services. It is not the official riversidecounty.gov website.',
      departmentsHeading: 'Departments',
      legalHeading: 'Legal',
      privacy: 'Privacy Policy',
      terms: 'Terms of Use',
      accessibility: 'Accessibility Statement',
      emergencyHeading: 'Emergency Contacts',
      infoCenter: 'County Information Center (non-emergency)',
      emergency: 'Emergency — Police / Fire / Medical',
      copyright: 'Riverside County Government. All rights reserved. (Demo build)',
      builtWith: 'Built to demonstrate WSO2 Agent Manager multi-department agent instances.',
    },
    chat: {
      typePlaceholder: 'Type your message...',
      send: 'Send',
      clearChat: 'Clear chat',
      close: 'Close',
      openChat: 'Open chat',
      liveModeNotice: 'Live mode — sending real requests to localhost',
      checkoutTitle: 'Municipal Portal Checkout',
      checkoutSubtitle: 'Simulated payment gateway — no real transaction occurs',
      cardNumberLabel: 'Card Number (demo)',
      expiryLabel: 'Expiry',
      cvvLabel: 'CVV',
      cancel: 'Cancel',
      confirmPayment: 'Confirm Payment',
      processing: 'Processing',
      unknownAgent: 'Unknown agent',
      assistedBy: 'Assisted by',
      onPremBadge: 'On-Prem · PII Restricted',
      cloudBadge: 'Cloud OK',
      greeting: (name) => `Hello! I'm the ${name}. How can I help you today?`,
    },
    tax: {
      hintTitle: 'Try it',
      hint: 'Ask: "Pay Q1 assessment rates for PROP-RVC-2026-88" to see the prompt-payment discount and online checkout flow.',
    },
    social: {
      citizenTab: 'Citizen Services',
      caseworkerTab: 'Caseworker Portal',
      oboTitle: 'On-Behalf-Of (OBO) Access Control',
      oboText: 'This agent only shows cases assigned to the active caseworker. Switch personas below to see the security notice in action.',
      activeCaseworker: 'Active Caseworker',
      tryAsJoan: 'Try asking as Joan Ellis: "Summarize case CASE-2026-002" — assigned to Marcus Lee — to see the access-denied security notice.',
    },
    permits: {
      servicesInDivision: 'Services in this division',
      isolationNote: 'Each division runs as an independent agent instance with its own database — a Building Permits status lookup will never see a Business Licenses application, and vice versa.',
    },
    records: {
      rtiTitle: 'Freedom of Information Act (FOIA)',
      rtiText: 'Some records are exempt from disclosure (e.g. active investigations). Disclosable records automatically have PII redacted before release.',
      tryIt: 'Try: "Retrieve public record REC-2026-101" (redacted PII) or "Retrieve public record REC-2026-102" (statutory exemption).',
    },
    contact: {
      hotlineLabel: 'County Info Hotline',
    },
    officers: {
      designations: {
        informationOfficer: 'Information Officer',
        citizenServicesOfficer: 'Citizen Services Officer',
        contactCenterCoordinator: 'Contact Center Coordinator',
        socialServicesOfficer: 'Social Services Officer',
        welfareBenefitsOfficer: 'Welfare Benefits Officer',
        eligibilityAssessor: 'Eligibility Assessor',
        seniorCaseworker: 'Senior Caseworker',
        caseworker: 'Caseworker',
        buildingInspector: 'Building Inspector',
        permitsOfficer: 'Permits Officer',
        licensingOfficer: 'Licensing Officer',
        tradeLicenseOfficer: 'Trade License Officer',
        seniorRevenueInspector: 'Senior Revenue Inspector',
        assessmentOfficer: 'Assessment Officer',
        revenueCollector: 'Revenue Collector',
        recordsComplianceOfficer: 'Records & Compliance Officer',
      },
    },
    agents: {
      citizenInquiry: { name: 'Citizen Inquiry Agent', department: 'Riverside County Department of Citizen Services' },
      welfareEligibility: { name: 'Welfare & Eligibility Assistant', department: 'Riverside County Department of Social Services' },
      planningPermits: { name: 'Planning & Permits Assistant', department: 'Riverside County Permits & Licensing' },
      taxRevenueAssistant: { name: 'Tax & Revenue Rate Assistant', department: 'Riverside County Tax & Revenue' },
      recordsFoiaBrand: { name: 'Public Records & FOIA Assistant', department: 'Riverside County Records & Compliance' },
      benefitsEligibility: { name: 'Benefits Eligibility Agent', department: 'Riverside County Department of Social Services' },
      caseManagement: { name: 'Case Management Agent', department: 'Riverside County Department of Social Services (Caseworker)' },
      permitsBuilding: { name: 'Permit & Licensing Agent — Building Permits', department: 'Riverside County Permits & Licensing' },
      permitsBusiness: {
        name: 'Permit & Licensing Agent — Business & Trade Licenses',
        department: 'Riverside County Permits & Licensing',
      },
      taxAssistance: { name: 'Tax & Assessment Agent', department: 'Riverside County Tax & Revenue' },
      recordsFoia: { name: 'Records / FOIA Agent', department: 'Riverside County Records & Compliance' },
    },
    pages: {
      home: {
        deptDirectory: 'Department Directory',
        deptDirectorySub: '6 Agent Kinds · ~10 running instances',
        askInquiry: 'Ask the Citizen Inquiry Agent',
        askInquirySub: 'Central Contact Center assistant',
      },
      contactCenter: { title: 'Contact Center', description: 'General inquiries, service directory, and SLA information for all departments.' },
      socialServices: {
        title: 'Riverside County Department of Social Services',
        description: 'Welfare benefits, senior citizen allowances, medical aid, and caseworker case management.',
      },
      permits: {
        title: 'Riverside County Permits & Licensing',
        description: 'Building plan approvals, street line certificates, and trade/business licenses.',
      },
      taxRevenue: { title: 'Riverside County Tax & Revenue', description: 'Property assessment rates, trade tax tiers, and online rate payments.' },
      records: {
        title: 'Riverside County Records & Compliance',
        description: 'Public records (FOIA) requests, disclosure exemption checks, and civil registration extracts.',
      },
    },
    services: {
      'general-faq': { title: 'General FAQs', description: 'Common questions about municipal services.' },
      'service-directory': { title: 'Service Directory', description: 'Find the right department for your need.' },
      'sla-lookup': { title: 'SLA Enquiries', description: 'Check standard processing timelines.' },
      'senior-allowance': { title: 'Senior Citizen Allowance', description: 'Monthly allowance for citizens aged 60+.' },
      'medical-aid': { title: 'Medical Low-Income Aid', description: 'Support for medical equipment and treatment costs.' },
      'public-assistance': { title: 'Public Assistance Allowance', description: 'Income-based household support.' },
      'building-plan': { title: 'Building Plan Approval', description: 'Submit and track building plan applications.' },
      'street-line': { title: 'Street Line Certificate', description: 'Boundary and road reservation certification.' },
      'trade-license': { title: 'Trade Business License', description: 'Register and renew a trade license.' },
      'assessment-rates': { title: 'Assessment Rates Payment', description: 'Pay quarterly property assessment rates online.' },
      'non-arrears': { title: 'Non-Arrears Certificate', description: 'Confirm your property has no outstanding balance.' },
      'trade-tax': { title: 'Trade Tax Collection', description: 'Business trade tax tiers and payment.' },
      'foia-request': { title: 'Public Records Request', description: 'Submit a Freedom of Information Act (FOIA) request.' },
      'birth-death-marriage': { title: 'Birth / Death / Marriage Extracts', description: 'Request certified civil registration extracts.' },
      grievance: { title: 'Public Complaints & Grievances', description: 'Lodge a formal complaint with the county.' },
    },
    quickReplyLabels: {
      'What are the opening hours for the Municipal Office?': 'What are the opening hours for the Municipal Office?',
      'Where do I pay my assessment rates?': 'Where do I pay my assessment rates?',
      'How do I request a birth certificate extract?': 'How do I request a birth certificate extract?',
      'Am I eligible for the Senior Citizen Allowance?': 'Am I eligible for the Senior Citizen Allowance?',
      'What documents do I need for medical low-income aid?': 'What documents do I need for medical low-income aid?',
      'Check my application status': 'Check my application status',
      'Summarize case CASE-2026-001': 'Summarize case CASE-2026-001',
      'Summarize case CASE-2026-002': 'Summarize case CASE-2026-002',
      'Draft next steps': 'Draft next steps',
      'Check status for Applicant ID 198204100V': 'Check status for Applicant ID 198204100V',
      'What documents do I need for a Building Plan?': 'What documents do I need for a Building Plan?',
      'Check status for Applicant ID 199012300V': 'Check status for Applicant ID 199012300V',
      'What documents do I need for a Trade License?': 'What documents do I need for a Trade License?',
      'Check my rates balance': 'Check my rates balance',
      'Pay Q1 assessment rates for PROP-RVC-2026-88': 'Pay Q1 assessment rates for PROP-RVC-2026-88',
      'What are the trade tax tiers?': 'What are the trade tax tiers?',
      'Retrieve public record REC-2026-101': 'Retrieve public record REC-2026-101',
      'Retrieve public record REC-2026-102': 'Retrieve public record REC-2026-102',
      'Submit a FOIA request': 'Submit a FOIA request',
    },
    mockResponses: {
      citizenInquiry: {
        hours: 'Riverside County Administration offices are open Mon-Fri, 8:30 AM - 4:15 PM. For urgent inquiries, call 311.',
        civilRegistration:
          'Birth, death, and marriage extracts are handled by the Department of Records & Compliance. Visit the Records & Compliance page to submit a request.',
        assessmentRates:
          'Assessment rates are paid quarterly through the Tax & Revenue Department — at the Payment Counter, or online via the Tax & Assessment Agent.',
        fallback:
          "I'm not certain about that yet in this demo — try asking about county office hours, assessment rate payments, or civil registration extracts.",
      },
      benefitsEligibility: {
        askAgeIncome:
          'To check your eligibility for the Senior Citizen Allowance, could you tell me your age and your monthly household income?',
        eligible: (age, income) =>
          `Status: Eligible. Monthly Allowance: $250. Based on age ${age} and monthly income $${income.toLocaleString()}, you pre-qualify for the Senior Citizen Allowance. Final eligibility is confirmed after document verification.`,
        notEligible: (age, income) =>
          `Status: Not Eligible. Based on age ${age} and monthly income $${income.toLocaleString()}, you do not currently meet the pre-screening thresholds (age 60+, income at or below $2,000/month).`,
        medicalAid:
          'For medical low-income aid you will need: a completed Medical Assistance Application Form, an Applicant ID copy, a county caseworker income certificate, and supporting medical documents.',
        askStatus: 'Please share your Applicant ID or application ID so I can look up your benefits application status.',
        fallback:
          'I can help assess eligibility for the senior citizen allowance, medical low-income aid, or public assistance. Try asking about one of those.',
      },
      caseManagement: {
        notFound: (caseId) => `No case found with ID '${caseId}'.`,
        denied: (caseId, ownerLabel) =>
          `Security Notice: Access Denied. Case ${caseId} is assigned to ${ownerLabel}, not to you. You may only view cases assigned to your own caseload.`,
        summary: (caseId, citizen, status) => `Case ${caseId}: ${citizen}'s case is currently ${status}.`,
        fallback: 'Please provide a case ID (e.g. CASE-2026-001) so I can look it up.',
      },
      permits: {
        notFound: (division, nic) =>
          `No ${division === 'building' ? 'building permit' : 'trade license'} application found for Applicant ID ${nic} in this division.`,
        statusIntro: (appId, name, status) => `Application ${appId} for ${name} — Status: ${status}.`,
        fallbackBuilding: 'Please provide an Applicant ID number so I can check your Building Permit application status.',
        fallbackBusiness: 'Please provide an Applicant ID number so I can check your Trade License application status.',
      },
      taxAssistance: {
        discountIntro: (base, discountPct, net) =>
          `Property PROP-RVC-2026-88 — Q1 assessment rate is $${base.toLocaleString()}. A ${discountPct}% prompt payment discount applies, bringing your total to $${net.toLocaleString()}.`,
        tradeTaxTiers:
          'Trade tax has three tiers: Tier A (small scale, $100–500/yr), Tier B (medium scale, $500–2,000/yr), and Tier C (large scale/corporate, $2,000–5,000+/yr).',
        nonArrearsAsk: 'Please share your assessment number so I can check the non-arrears status for that property.',
        balanceAsk: 'Please share your assessment number (e.g. PROP-RVC-2026-88) so I can look up your current balance.',
        fallback: 'I can help with assessment rate payments, non-arrears status, or trade tax tiers. Try asking about one of those.',
        receiptIntro: 'Your payment has been received and settled. Here is your digital receipt.',
        payOnline: 'Pay Online (Municipal Portal)',
      },
      recordsFoia: {
        notFound: (recordId) => `No public record found with ID '${recordId}'.`,
        exemptionRefused: (reason) => `Disclosure Refused: ${reason}`,
        disclosableIntro: (recordId, title, category) => `Record ${recordId}: ${title} (Category: ${category})`,
        foiaLogged: (requestId) => `Your public records request has been logged. Request ID: ${requestId} (status: RECEIVED).`,
        fallback: 'Please provide a record ID (e.g. REC-2026-101) or ask to submit a public records request.',
      },
    },
  },
}

export function translate(lang, path) {
  const dict = translations[lang] || translations.en
  const fallback = translations.en
  const value = path.split('.').reduce((acc, key) => (acc == null ? acc : acc[key]), dict)
  if (value !== undefined) return value
  return path.split('.').reduce((acc, key) => (acc == null ? acc : acc[key]), fallback)
}
