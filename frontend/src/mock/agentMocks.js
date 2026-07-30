/**
 * Mock agent engine. Simulates streaming tool-execution steps and a final
 * answer (with an optional structured "card" payload) for each of the 6
 * agent kinds, without requiring any backend to be running.
 *
 * Swapped out for real POST /chat calls in src/services/agentApi.js when
 * VITE_USE_MOCK_AGENTS=false.
 */

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

function extractNumbers(text) {
  return (text.match(/\d+(\.\d+)?/g) || []).map(Number)
}

// ---------------------------------------------------------------------------
// Citizen Inquiry Agent
// ---------------------------------------------------------------------------
function resolveCitizenInquiry(message) {
  const m = message.toLowerCase()

  if (m.includes('hours') || m.includes('municipal council') || m.includes('municipal office')) {
    return {
      steps: ['Searching Knowledge Base...'],
      text: 'The Municipal Council offices are open Monday through Friday from 8:30 AM to 4:15 PM. For urgent assistance, contact the Government Information Center at 1919.',
      card: null,
    }
  }
  if (m.includes('birth') || m.includes('death') || m.includes('marriage') || m.includes('extract')) {
    return {
      steps: ['Searching Knowledge Base...'],
      text: 'Birth, death, and marriage extracts are handled by the Department of Records & Compliance. Visit the Records & Compliance page to submit a request.',
      card: null,
    }
  }
  if (m.includes('assessment') || (m.includes('pay') && m.includes('rate'))) {
    return {
      steps: ['Searching Knowledge Base...'],
      text: 'Assessment rates are paid quarterly through the Tax & Revenue Department — at the Shroff Counter, or online via the Tax & Assessment Agent.',
      card: null,
    }
  }
  return null
}

// ---------------------------------------------------------------------------
// Benefits Eligibility Agent
// ---------------------------------------------------------------------------
function resolveBenefitsEligibility(message) {
  const m = message.toLowerCase()
  const numbers = extractNumbers(message)

  if (numbers.length >= 2 && (m.includes('year') || m.includes('income') || m.includes('earn') || m.includes('age') || m.includes('lkr'))) {
    const [age, income] = numbers
    const eligible = age >= 60 && income <= 15000
    return {
      steps: ['Consulting on-prem eligibility model...', 'Applying income & age pre-screening rules...'],
      text: eligible
        ? `Status: Eligible. Monthly Allowance: LKR 5,000. Based on age ${age} and monthly income LKR ${income.toLocaleString()}, you pre-qualify for the Senior Citizen Allowance. Final eligibility is confirmed after document verification.`
        : `Status: Not Eligible. Based on age ${age} and monthly income LKR ${income.toLocaleString()}, you do not currently meet the pre-screening thresholds (age 60+, income at or below LKR 15,000/month).`,
      card: eligible
        ? {
            type: 'eligibility',
            title: 'Pre-Screening Result',
            status: 'ELIGIBLE',
            badgeColor: 'emerald',
            fields: [
              { label: 'Benefit', value: 'Senior Citizen Allowance' },
              { label: 'Monthly Allowance', value: 'LKR 5,000' },
              { label: 'Age', value: String(age) },
              { label: 'Monthly Income', value: `LKR ${income.toLocaleString()}` },
            ],
          }
        : {
            type: 'eligibility',
            title: 'Pre-Screening Result',
            status: 'NOT ELIGIBLE',
            badgeColor: 'maroon',
            fields: [
              { label: 'Age', value: String(age) },
              { label: 'Monthly Income', value: `LKR ${income.toLocaleString()}` },
            ],
          },
    }
  }

  if (m.includes('senior citizen') && (m.includes('eligib') || m.includes('allowance'))) {
    return {
      steps: ['Reviewing eligibility policy...'],
      text: 'To check your eligibility for the Senior Citizen Allowance, could you tell me your age and your monthly household income?',
      card: null,
    }
  }

  if (m.includes('medical') && (m.includes('aid') || m.includes('document'))) {
    return {
      steps: ['Searching Knowledge Base...'],
      text: 'For medical low-income aid you will need: a completed Medical Assistance Application Form, a NIC copy, a Grama Niladhari income certificate, and supporting medical documents.',
      card: null,
    }
  }

  if (m.includes('status') || m.includes('application')) {
    return {
      steps: ['Querying application records...'],
      text: 'Please share your NIC or application ID so I can look up your benefits application status.',
      card: null,
    }
  }

  return null
}

// ---------------------------------------------------------------------------
// Case Management Agent (On-Behalf-Of scoping demo)
// ---------------------------------------------------------------------------
const CASES = {
  'CASE-2026-001': {
    owner: 'joan.ellis',
    ownerLabel: 'Joan Ellis',
    citizen: 'Sunethra Dias',
    caseType: 'BENEFITS_REVIEW',
    status: 'OPEN',
    notes: 'Initial intake complete. Awaiting income verification.',
  },
  'CASE-2026-002': {
    owner: 'marcus.lee',
    ownerLabel: 'Marcus Lee',
    citizen: 'Nimal Silva',
    caseType: 'MEDICAL_AID_ASSESSMENT',
    status: 'PENDING_REVIEW',
    notes: 'Medical report received.',
  },
}

function resolveCaseManagement(message, context) {
  const match = message.match(/CASE-\d{4}-\d{3}/i)
  if (!match) return null

  const caseId = match[0].toUpperCase()
  const record = CASES[caseId]
  const userId = context?.userId || 'joan.ellis'

  if (!record) {
    return { steps: ['Looking up case...'], text: `No case found with ID '${caseId}'.`, card: null }
  }

  if (record.owner !== userId) {
    return {
      steps: ['Looking up case...', 'Checking caseworker assignment (OBO)...'],
      text: `Security Notice: Access Denied. Case ${caseId} is assigned to ${record.ownerLabel}, not to you. You may only view cases assigned to your own caseload.`,
      card: {
        type: 'security-notice',
        title: 'Access Denied',
        status: 'DENIED',
        badgeColor: 'maroon',
        fields: [
          { label: 'Case ID', value: caseId },
          { label: 'Assigned To', value: record.ownerLabel },
          { label: 'Requested By', value: userId },
        ],
      },
    }
  }

  return {
    steps: ['Looking up case...', 'Checking caseworker assignment (OBO)...', 'Retrieving case notes...'],
    text: `Case ${caseId}: ${record.citizen}'s case is currently ${record.status}.`,
    card: {
      type: 'case-summary',
      title: `Case ${caseId}`,
      status: record.status,
      badgeColor: record.status === 'OPEN' ? 'gold' : 'emerald',
      fields: [
        { label: 'Citizen', value: record.citizen },
        { label: 'Case Type', value: record.caseType },
        { label: 'Status', value: record.status },
        { label: 'Notes', value: record.notes },
      ],
    },
  }
}

// ---------------------------------------------------------------------------
// Permit & Licensing Agent (Building / Business divisions)
// ---------------------------------------------------------------------------
const PERMIT_APPLICATIONS = {
  '198204100V': {
    division: 'building',
    appId: 'APP-BP-2026-104',
    name: 'Ariyawansa Gunasekera',
    status: 'APPROVED',
    permitType: 'BUILDING_PLAN',
  },
  '199012300V': {
    division: 'business',
    appId: 'APP-TL-2026-601',
    name: 'Chathurika Wickramasinghe',
    status: 'PENDING_INSPECTION',
    permitType: 'TRADE_LICENSE',
  },
}

function resolvePermits(message, division) {
  const match = message.match(/\d{9}[VvXx]/)
  if (!match) return null

  const nic = match[0].toUpperCase()
  const record = PERMIT_APPLICATIONS[nic]

  if (!record || record.division !== division) {
    return {
      steps: ['Querying Permit Database...'],
      text: `No ${division === 'building' ? 'building permit' : 'trade license'} application found for NIC ${nic} in this division.`,
      card: null,
    }
  }

  return {
    steps: ['Querying Permit Database...', 'Checking inspection schedule...'],
    text: `Application ${record.appId} for ${record.name} — Status: ${record.status}.`,
    card: {
      type: 'application-status',
      title: division === 'building' ? 'Building Permit Application' : 'Trade License Application',
      status: record.status,
      badgeColor: record.status === 'APPROVED' ? 'emerald' : 'gold',
      fields: [
        { label: 'Application ID', value: record.appId },
        { label: 'Applicant', value: record.name },
        { label: 'Permit Type', value: record.permitType },
        { label: 'Status', value: record.status },
      ],
    },
  }
}

// ---------------------------------------------------------------------------
// Tax & Assessment Agent
// ---------------------------------------------------------------------------
function resolveTaxAssistance(message) {
  const m = message.toLowerCase()

  if (m.includes('prop-col-2026-88') || (m.includes('pay') && (m.includes('assessment') || m.includes('rate')))) {
    const base = 12500
    const discountPct = 5
    const net = Math.round(base * (1 - discountPct / 100))
    return {
      steps: ['Checking Property Ledger...', 'Checking prompt payment discount window...', 'Calculating final amount...'],
      text: `Property PROP-COL-2026-88 — Q1 assessment rate is LKR ${base.toLocaleString()}. A ${discountPct}% prompt payment discount applies, bringing your total to LKR ${net.toLocaleString()}.`,
      card: {
        type: 'payment',
        title: 'Q1 Assessment Rate Payment',
        status: 'PENDING_GATEWAY',
        badgeColor: 'gold',
        fields: [
          { label: 'Assessment No.', value: 'PROP-COL-2026-88' },
          { label: 'Base Amount', value: `LKR ${base.toLocaleString()}` },
          { label: 'Prompt Payment Discount', value: `${discountPct}%` },
          { label: 'Net Amount Due', value: `LKR ${net.toLocaleString()}` },
        ],
        actions: [{ id: 'PAY_ONLINE', label: 'Pay Online (Municipal Portal)' }],
      },
    }
  }

  if (m.includes('trade tax') && m.includes('tier')) {
    return {
      steps: ['Searching Knowledge Base...'],
      text: 'Trade tax has three tiers: Tier A (small scale, LKR 1,000–5,000/yr), Tier B (medium scale, LKR 5,000–20,000/yr), and Tier C (large scale/corporate, LKR 20,000–50,000+/yr).',
      card: null,
    }
  }

  if (m.includes('non-arrears') || m.includes('arrears')) {
    return {
      steps: ['Checking Property Ledger...'],
      text: 'Please share your assessment number so I can check the non-arrears status for that property.',
      card: null,
    }
  }

  if (m.includes('balance') || m.includes('rates balance')) {
    return {
      steps: ['Checking Property Ledger...'],
      text: 'Please share your assessment number (e.g. PROP-COL-2026-88) so I can look up your current balance.',
      card: null,
    }
  }

  return null
}

function resolveTaxPaymentSettlement() {
  return {
    steps: ['Processing payment...', 'Verifying with bank (simulated)...', 'Generating digital receipt...'],
    text: 'Your payment has been received and settled. Here is your digital receipt.',
    card: {
      type: 'receipt',
      title: 'Municipal Tax Payment Receipt (Simulated)',
      status: 'PAID',
      badgeColor: 'emerald',
      fields: [
        { label: 'Receipt No.', value: 'RCT-2026-8801' },
        { label: 'Assessment No.', value: 'PROP-COL-2026-88' },
        { label: 'Period', value: 'Q1 2026' },
        { label: 'Amount Paid', value: 'LKR 11,875.00' },
        { label: 'Transaction ID', value: 'TXN-TAX-9901' },
        { label: 'Status', value: 'PAID' },
      ],
    },
  }
}

// ---------------------------------------------------------------------------
// Records / FOIA Agent
// ---------------------------------------------------------------------------
const PUBLIC_RECORDS = {
  'REC-2026-101': {
    title: '2025 City Center Maintenance Contract',
    category: 'MUNICIPAL_CONTRACT',
    exempt: false,
    content: 'Contractor: Apex Ltd. Total: $450,000. Contact: [REDACTED PII], Phone: [REDACTED PII]. SSN: [REDACTED PII].',
  },
  'REC-2026-102': {
    title: 'Internal Investigation on Property Zone 4',
    category: 'INTERNAL_MEMO',
    exempt: true,
    exemptionReason: 'Statutory Exemption 7(A) - Pending Law Enforcement Investigation',
  },
}

function resolveRecordsFoia(message) {
  const match = message.match(/REC-\d{4}-\d{3}/i)
  if (match) {
    const recordId = match[0].toUpperCase()
    const record = PUBLIC_RECORDS[recordId]

    if (!record) {
      return { steps: ['Querying Records Repository...'], text: `No public record found with ID '${recordId}'.`, card: null }
    }

    if (record.exempt) {
      return {
        steps: ['Querying Records Repository...', 'Validating Exemption...'],
        text: `Disclosure Refused: ${record.exemptionReason}`,
        card: {
          type: 'exemption-notice',
          title: `Record ${recordId}`,
          status: 'EXEMPT',
          badgeColor: 'maroon',
          fields: [
            { label: 'Title', value: record.title },
            { label: 'Category', value: record.category },
            { label: 'Exemption Reason', value: record.exemptionReason },
          ],
        },
      }
    }

    return {
      steps: ['Querying Records Repository...', 'Redacting PII...'],
      text: `Record ${recordId}: ${record.title} (Category: ${record.category})`,
      card: {
        type: 'redacted-record',
        title: `Record ${recordId}`,
        status: 'DISCLOSABLE',
        badgeColor: 'emerald',
        fields: [
          { label: 'Title', value: record.title },
          { label: 'Category', value: record.category },
          { label: 'Content', value: record.content },
        ],
      },
    }
  }

  if (/foia|public records request|submit/i.test(message)) {
    const requestId = `FOIA-${Math.random().toString(16).slice(2, 10).toUpperCase()}`
    return {
      steps: ['Logging request intake...'],
      text: `Your public records request has been logged. Request ID: ${requestId} (status: RECEIVED).`,
      card: null,
    }
  }

  return null
}

// ---------------------------------------------------------------------------
// Registry & runner
// ---------------------------------------------------------------------------
const RESOLVERS = {
  'citizen-inquiry': resolveCitizenInquiry,
  'benefits-eligibility': resolveBenefitsEligibility,
  'case-management': resolveCaseManagement,
  'permits-building': (msg) => resolvePermits(msg, 'building'),
  'permits-business': (msg) => resolvePermits(msg, 'business'),
  'tax-assistance': resolveTaxAssistance,
  'records-foia': resolveRecordsFoia,
}

const FALLBACKS = {
  'citizen-inquiry':
    "I'm not certain about that yet in this demo — try asking about council working hours, assessment rate payments, or civil registration extracts.",
  'benefits-eligibility':
    'I can help assess eligibility for the senior citizen allowance, medical low-income aid, or public assistance. Try asking about one of those.',
  'case-management': 'Please provide a case ID (e.g. CASE-2026-001) so I can look it up.',
  'permits-building': 'Please provide a NIC number so I can check your Building Permit application status.',
  'permits-business': 'Please provide a NIC number so I can check your Trade License application status.',
  'tax-assistance': 'I can help with assessment rate payments, non-arrears status, or trade tax tiers. Try asking about one of those.',
  'records-foia': 'Please provide a record ID (e.g. REC-2026-101) or ask to submit a public records request.',
}

/**
 * Run a mock agent turn. Calls `onStep(label)` for each simulated
 * tool-execution step before resolving with the final `{ text, card }`.
 */
export async function runMockAgent({ agentKey, message, context = {}, onStep }) {
  const resolver = RESOLVERS[agentKey]
  const resolved = resolver ? resolver(message, context) : null
  const result = resolved || {
    steps: ['Thinking...'],
    text: FALLBACKS[agentKey] || "I'm not sure how to help with that in this demo.",
    card: null,
  }

  for (const step of result.steps) {
    onStep?.(step)
    await delay(500 + Math.random() * 350)
  }
  await delay(250)

  return { text: result.text, card: result.card || null }
}

/**
 * Handle a card action (e.g. clicking "Pay Online" on the tax payment card).
 */
export async function runMockCardAction({ agentKey, actionId, onStep }) {
  if (agentKey === 'tax-assistance' && actionId === 'PAY_ONLINE') {
    const result = resolveTaxPaymentSettlement()
    for (const step of result.steps) {
      onStep?.(step)
      await delay(500 + Math.random() * 350)
    }
    await delay(250)
    return { text: result.text, card: result.card }
  }
  return { text: 'This action is not available in the demo.', card: null }
}
