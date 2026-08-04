/**
 * Mock agent engine. Simulates streaming tool-execution steps and a final
 * answer (with an optional structured "card" payload) for each of the 6
 * agent kinds, without requiring any backend to be running. Every string
 * shown to the user (steps, body text, card labels/status) comes from the
 * TEXT dictionary below (English only).
 *
 * Swapped out for real POST /chat calls in src/services/agentApi.js when
 * VITE_USE_MOCK_AGENTS=false.
 */

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

function extractNumbers(text) {
  return (text.match(/\d+(\.\d+)?/g) || []).map(Number)
}

const STEPS = {
  en: {
    searchingKb: 'Searching Knowledge Base...',
    consultingModel: 'Consulting on-prem eligibility model...',
    applyingRules: 'Applying income & age pre-screening rules...',
    reviewingPolicy: 'Reviewing eligibility policy...',
    queryingApplications: 'Querying application records...',
    lookingUpCase: 'Looking up case...',
    checkingObo: 'Checking caseworker assignment (OBO)...',
    retrievingNotes: 'Retrieving case notes...',
    queryingPermitDb: 'Querying Permit Database...',
    checkingInspection: 'Checking inspection schedule...',
    checkingLedger: 'Checking Property Ledger...',
    checkingDiscountWindow: 'Checking prompt payment discount window...',
    calculatingAmount: 'Calculating final amount...',
    processingPayment: 'Processing payment...',
    verifyingBank: 'Verifying with bank (simulated)...',
    generatingReceipt: 'Generating digital receipt...',
    queryingRecordsRepo: 'Querying Records Repository...',
    validatingExemption: 'Validating Exemption...',
    redactingPii: 'Redacting PII...',
    loggingIntake: 'Logging request intake...',
    thinking: 'Thinking...',
  },
}

const TEXT = {
  en: {
    citizen: {
      officeHours:
        'The Municipal Council offices are open Monday through Friday from 8:30 AM to 4:15 PM. For urgent assistance, contact the Riverside County Information Center at 311.',
      birthDeathMarriage:
        'Birth, death, and marriage extracts are handled by the Department of Records & Compliance. Visit the Records & Compliance page to submit a request.',
      assessmentRoute:
        'Assessment rates are paid quarterly through the Tax & Revenue Department — at the Payment Counter, or online via the Tax & Assessment Agent.',
      fallback:
        "I'm not certain about that yet in this demo — try asking about council working hours, assessment rate payments, or civil registration extracts.",
    },
    benefits: {
      eligible: (age, income) =>
        `Status: Eligible. Monthly Allowance: $250. Based on age ${age} and monthly income $${income.toLocaleString()}, you pre-qualify for the Senior Citizen Allowance. Final eligibility is confirmed after document verification.`,
      notEligible: (age, income) =>
        `Status: Not Eligible. Based on age ${age} and monthly income $${income.toLocaleString()}, you do not currently meet the pre-screening thresholds (age 60+, income at or below $2,000/month).`,
      askAgeIncome: 'To check your eligibility for the Senior Citizen Allowance, could you tell me your age and your monthly household income?',
      medicalAidDocs:
        'For medical low-income aid you will need: a completed Medical Assistance Application Form, an Applicant ID copy, a county caseworker income certificate, and supporting medical documents.',
      statusAskId: 'Please share your Applicant ID or application ID so I can look up your benefits application status.',
      fallback:
        'I can help assess eligibility for the senior citizen allowance, medical low-income aid, or public assistance. Try asking about one of those.',
      cardTitle: 'Pre-Screening Result',
      statusEligible: 'ELIGIBLE',
      statusNotEligible: 'NOT ELIGIBLE',
      fields: { benefit: 'Benefit', monthlyAllowance: 'Monthly Allowance', age: 'Age', monthlyIncome: 'Monthly Income' },
      benefitName: 'Senior Citizen Allowance',
      allowanceAmount: '$250',
    },
    case: {
      noCase: (id) => `No case found with ID '${id}'.`,
      accessDenied: (id, owner) =>
        `Security Notice: Access Denied. Case ${id} is assigned to ${owner}, not to you. You may only view cases assigned to your own caseload.`,
      summary: (id, citizen, status) => `Case ${id}: ${citizen}'s case is currently ${status}.`,
      fallback: 'Please provide a case ID (e.g. CASE-2026-001) so I can look it up.',
      accessDeniedTitle: 'Access Denied',
      caseTitlePrefix: 'Case',
      statusDenied: 'DENIED',
      fields: { caseId: 'Case ID', assignedTo: 'Assigned To', requestedBy: 'Requested By', citizen: 'Citizen', caseType: 'Case Type', status: 'Status', notes: 'Notes' },
    },
    permits: {
      notFound: (kind, nic) => `No ${kind} application found for Applicant ID ${nic} in this division.`,
      statusLine: (appId, name, status) => `Application ${appId} for ${name} — Status: ${status}.`,
      buildingKind: 'building permit',
      tradeKind: 'trade license',
      cardTitleBuilding: 'Building Permit Application',
      cardTitleTrade: 'Trade License Application',
      fields: { applicationId: 'Application ID', applicant: 'Applicant', permitType: 'Permit Type', status: 'Status' },
      fallbackBuilding: 'Please provide an Applicant ID number so I can check your Building Permit application status.',
      fallbackBusiness: 'Please provide an Applicant ID number so I can check your Trade License application status.',
    },
    tax: {
      assessmentLine: (base, discountPct, net) =>
        `Property PROP-RVC-2026-88 — Q1 assessment rate is $${base.toLocaleString()}. A ${discountPct}% prompt payment discount applies, bringing your total to $${net.toLocaleString()}.`,
      tradeTaxTiers:
        'Trade tax has three tiers: Tier A (small scale, $100–500/yr), Tier B (medium scale, $500–2,000/yr), and Tier C (large scale/corporate, $2,000–5,000+/yr).',
      nonArrearsAsk: 'Please share your assessment number so I can check the non-arrears status for that property.',
      balanceAsk: 'Please share your assessment number (e.g. PROP-RVC-2026-88) so I can look up your current balance.',
      fallback: 'I can help with assessment rate payments, non-arrears status, or trade tax tiers. Try asking about one of those.',
      cardTitle: 'Q1 Assessment Rate Payment',
      payOnlineAction: 'Pay Online (Municipal Portal)',
      statusPendingGateway: 'PENDING_GATEWAY',
      fields: { assessmentNo: 'Assessment No.', baseAmount: 'Base Amount', discount: 'Prompt Payment Discount', netDue: 'Net Amount Due' },
      receiptText: 'Your payment has been received and settled. Here is your digital receipt.',
      receiptCardTitle: 'Municipal Tax Payment Receipt (Simulated)',
      statusPaid: 'PAID',
      receiptFields: { receiptNo: 'Receipt No.', assessmentNo: 'Assessment No.', period: 'Period', amountPaid: 'Amount Paid', transactionId: 'Transaction ID', status: 'Status' },
    },
    records: {
      notFound: (id) => `No public record found with ID '${id}'.`,
      exemptText: (reason) => `Disclosure Refused: ${reason}`,
      exemptionReason: 'Statutory Exemption 7(A) - Pending Law Enforcement Investigation',
      disclosableText: (id, title, category) => `Record ${id}: ${title} (Category: ${category})`,
      foiaLogged: (id) => `Your public records request has been logged. Request ID: ${id} (status: RECEIVED).`,
      fallback: 'Please provide a record ID (e.g. REC-2026-101) or ask to submit a public records request.',
      exemptCardTitlePrefix: 'Record',
      statusExempt: 'EXEMPT',
      statusDisclosable: 'DISCLOSABLE',
      fields: { title: 'Title', category: 'Category', exemptionReason: 'Exemption Reason', content: 'Content' },
      record101Title: '2025 City Center Maintenance Contract',
      record101Content: 'Contractor: Apex Ltd. Total: $450,000. Contact: [REDACTED PII], Phone: [REDACTED PII]. SSN: [REDACTED PII].',
      record102Title: 'Internal Investigation on Property Zone 4',
    },
  },
}

function stepsFor(lang, keys) {
  const dict = STEPS[lang] || STEPS.en
  return keys.map((k) => dict[k])
}

// ---------------------------------------------------------------------------
// Citizen Inquiry Agent
// ---------------------------------------------------------------------------
function resolveCitizenInquiry(message, lang) {
  const m = message.toLowerCase()
  const T = TEXT[lang] || TEXT.en

  if (m.includes('hours') || m.includes('municipal council') || m.includes('municipal office')) {
    return { steps: stepsFor(lang, ['searchingKb']), text: T.citizen.officeHours, card: null }
  }
  if (m.includes('birth') || m.includes('death') || m.includes('marriage') || m.includes('extract')) {
    return { steps: stepsFor(lang, ['searchingKb']), text: T.citizen.birthDeathMarriage, card: null }
  }
  if (m.includes('assessment') || (m.includes('pay') && m.includes('rate'))) {
    return { steps: stepsFor(lang, ['searchingKb']), text: T.citizen.assessmentRoute, card: null }
  }
  return null
}

// ---------------------------------------------------------------------------
// Benefits Eligibility Agent
// ---------------------------------------------------------------------------
function resolveBenefitsEligibility(message, lang) {
  const m = message.toLowerCase()
  const numbers = extractNumbers(message)
  const T = (TEXT[lang] || TEXT.en).benefits

  if (numbers.length >= 2 && (m.includes('year') || m.includes('income') || m.includes('earn') || m.includes('age') || m.includes('usd'))) {
    const [age, income] = numbers
    const eligible = age >= 60 && income <= 2000
    return {
      steps: stepsFor(lang, ['consultingModel', 'applyingRules']),
      text: eligible ? T.eligible(age, income) : T.notEligible(age, income),
      card: eligible
        ? {
            type: 'eligibility',
            title: T.cardTitle,
            status: T.statusEligible,
            badgeColor: 'emerald',
            fields: [
              { label: T.fields.benefit, value: T.benefitName },
              { label: T.fields.monthlyAllowance, value: T.allowanceAmount },
              { label: T.fields.age, value: String(age) },
              { label: T.fields.monthlyIncome, value: `$${income.toLocaleString()}` },
            ],
          }
        : {
            type: 'eligibility',
            title: T.cardTitle,
            status: T.statusNotEligible,
            badgeColor: 'maroon',
            fields: [
              { label: T.fields.age, value: String(age) },
              { label: T.fields.monthlyIncome, value: `$${income.toLocaleString()}` },
            ],
          },
    }
  }

  if (m.includes('senior citizen') && (m.includes('eligib') || m.includes('allowance'))) {
    return { steps: stepsFor(lang, ['reviewingPolicy']), text: T.askAgeIncome, card: null }
  }

  if (m.includes('medical') && (m.includes('aid') || m.includes('document'))) {
    return { steps: stepsFor(lang, ['searchingKb']), text: T.medicalAidDocs, card: null }
  }

  if (m.includes('status') || m.includes('application')) {
    return { steps: stepsFor(lang, ['queryingApplications']), text: T.statusAskId, card: null }
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
    citizen: 'Sandra Wells',
    caseType: 'BENEFITS_REVIEW',
    status: 'OPEN',
    notes: 'Initial intake complete. Awaiting income verification.',
  },
  'CASE-2026-002': {
    owner: 'marcus.lee',
    ownerLabel: 'Marcus Lee',
    citizen: 'David Cole',
    caseType: 'MEDICAL_AID_ASSESSMENT',
    status: 'PENDING_REVIEW',
    notes: 'Medical report received.',
  },
}

function resolveCaseManagement(message, lang, context) {
  const match = message.match(/CASE-\d{4}-\d{3}/i)
  if (!match) return null

  const T = (TEXT[lang] || TEXT.en).case
  const caseId = match[0].toUpperCase()
  const record = CASES[caseId]
  const userId = context?.userId || 'joan.ellis'

  if (!record) {
    return { steps: stepsFor(lang, ['lookingUpCase']), text: T.noCase(caseId), card: null }
  }

  if (record.owner !== userId) {
    return {
      steps: stepsFor(lang, ['lookingUpCase', 'checkingObo']),
      text: T.accessDenied(caseId, record.ownerLabel),
      card: {
        type: 'security-notice',
        title: T.accessDeniedTitle,
        status: T.statusDenied,
        badgeColor: 'maroon',
        fields: [
          { label: T.fields.caseId, value: caseId },
          { label: T.fields.assignedTo, value: record.ownerLabel },
          { label: T.fields.requestedBy, value: userId },
        ],
      },
    }
  }

  return {
    steps: stepsFor(lang, ['lookingUpCase', 'checkingObo', 'retrievingNotes']),
    text: T.summary(caseId, record.citizen, record.status),
    card: {
      type: 'case-summary',
      title: `${T.caseTitlePrefix} ${caseId}`,
      status: record.status,
      badgeColor: record.status === 'OPEN' ? 'gold' : 'emerald',
      fields: [
        { label: T.fields.citizen, value: record.citizen },
        { label: T.fields.caseType, value: record.caseType },
        { label: T.fields.status, value: record.status },
        { label: T.fields.notes, value: record.notes },
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
    name: 'Robert Hayes',
    status: 'APPROVED',
    permitType: 'BUILDING_PLAN',
  },
  '199012300V': {
    division: 'business',
    appId: 'APP-TL-2026-601',
    name: 'Maria Alvarez',
    status: 'PENDING_INSPECTION',
    permitType: 'TRADE_LICENSE',
  },
}

function resolvePermits(message, lang, division) {
  const match = message.match(/\d{9}[VvXx]/)
  if (!match) return null

  const T = (TEXT[lang] || TEXT.en).permits
  const nic = match[0].toUpperCase()
  const record = PERMIT_APPLICATIONS[nic]
  const kindLabel = division === 'building' ? T.buildingKind : T.tradeKind

  if (!record || record.division !== division) {
    return { steps: stepsFor(lang, ['queryingPermitDb']), text: T.notFound(kindLabel, nic), card: null }
  }

  return {
    steps: stepsFor(lang, ['queryingPermitDb', 'checkingInspection']),
    text: T.statusLine(record.appId, record.name, record.status),
    card: {
      type: 'application-status',
      title: division === 'building' ? T.cardTitleBuilding : T.cardTitleTrade,
      status: record.status,
      badgeColor: record.status === 'APPROVED' ? 'emerald' : 'gold',
      fields: [
        { label: T.fields.applicationId, value: record.appId },
        { label: T.fields.applicant, value: record.name },
        { label: T.fields.permitType, value: record.permitType },
        { label: T.fields.status, value: record.status },
      ],
    },
  }
}

// ---------------------------------------------------------------------------
// Tax & Assessment Agent
// ---------------------------------------------------------------------------
function resolveTaxAssistance(message, lang) {
  const m = message.toLowerCase()
  const T = (TEXT[lang] || TEXT.en).tax

  if (m.includes('prop-col-2026-88') || (m.includes('pay') && (m.includes('assessment') || m.includes('rate')))) {
    const base = 1250
    const discountPct = 5
    const net = Math.round(base * (1 - discountPct / 100))
    return {
      steps: stepsFor(lang, ['checkingLedger', 'checkingDiscountWindow', 'calculatingAmount']),
      text: T.assessmentLine(base, discountPct, net),
      card: {
        type: 'payment',
        title: T.cardTitle,
        status: T.statusPendingGateway,
        badgeColor: 'gold',
        fields: [
          { label: T.fields.assessmentNo, value: 'PROP-RVC-2026-88' },
          { label: T.fields.baseAmount, value: `$${base.toLocaleString()}` },
          { label: T.fields.discount, value: `${discountPct}%` },
          { label: T.fields.netDue, value: `$${net.toLocaleString()}` },
        ],
        actions: [{ id: 'PAY_ONLINE', label: T.payOnlineAction }],
      },
    }
  }

  if (m.includes('trade tax') && m.includes('tier')) {
    return { steps: stepsFor(lang, ['searchingKb']), text: T.tradeTaxTiers, card: null }
  }

  if (m.includes('non-arrears') || m.includes('arrears')) {
    return { steps: stepsFor(lang, ['checkingLedger']), text: T.nonArrearsAsk, card: null }
  }

  if (m.includes('balance') || m.includes('rates balance')) {
    return { steps: stepsFor(lang, ['checkingLedger']), text: T.balanceAsk, card: null }
  }

  return null
}

function resolveTaxPaymentSettlement(lang) {
  const T = (TEXT[lang] || TEXT.en).tax
  return {
    steps: stepsFor(lang, ['processingPayment', 'verifyingBank', 'generatingReceipt']),
    text: T.receiptText,
    card: {
      type: 'receipt',
      title: T.receiptCardTitle,
      status: T.statusPaid,
      badgeColor: 'emerald',
      fields: [
        { label: T.receiptFields.receiptNo, value: 'RCT-2026-8801' },
        { label: T.receiptFields.assessmentNo, value: 'PROP-RVC-2026-88' },
        { label: T.receiptFields.period, value: 'Q1 2026' },
        { label: T.receiptFields.amountPaid, value: '$1,187.50' },
        { label: T.receiptFields.transactionId, value: 'TXN-TAX-9901' },
        { label: T.receiptFields.status, value: T.statusPaid },
      ],
    },
  }
}

// ---------------------------------------------------------------------------
// Records / FOIA Agent
// ---------------------------------------------------------------------------
function buildPublicRecords(lang) {
  const T = (TEXT[lang] || TEXT.en).records
  return {
    'REC-2026-101': {
      title: T.record101Title,
      category: 'MUNICIPAL_CONTRACT',
      exempt: false,
      content: T.record101Content,
    },
    'REC-2026-102': {
      title: T.record102Title,
      category: 'INTERNAL_MEMO',
      exempt: true,
      exemptionReason: T.exemptionReason,
    },
  }
}

function resolveRecordsFoia(message, lang) {
  const T = (TEXT[lang] || TEXT.en).records
  const match = message.match(/REC-\d{4}-\d{3}/i)
  if (match) {
    const recordId = match[0].toUpperCase()
    const record = buildPublicRecords(lang)[recordId]

    if (!record) {
      return { steps: stepsFor(lang, ['queryingRecordsRepo']), text: T.notFound(recordId), card: null }
    }

    if (record.exempt) {
      return {
        steps: stepsFor(lang, ['queryingRecordsRepo', 'validatingExemption']),
        text: T.exemptText(record.exemptionReason),
        card: {
          type: 'exemption-notice',
          title: `${T.exemptCardTitlePrefix} ${recordId}`,
          status: T.statusExempt,
          badgeColor: 'maroon',
          fields: [
            { label: T.fields.title, value: record.title },
            { label: T.fields.category, value: record.category },
            { label: T.fields.exemptionReason, value: record.exemptionReason },
          ],
        },
      }
    }

    return {
      steps: stepsFor(lang, ['queryingRecordsRepo', 'redactingPii']),
      text: T.disclosableText(recordId, record.title, record.category),
      card: {
        type: 'redacted-record',
        title: `${T.exemptCardTitlePrefix} ${recordId}`,
        status: T.statusDisclosable,
        badgeColor: 'emerald',
        fields: [
          { label: T.fields.title, value: record.title },
          { label: T.fields.category, value: record.category },
          { label: T.fields.content, value: record.content },
        ],
      },
    }
  }

  if (/foia|public records request|submit/i.test(message)) {
    const requestId = `FOIA-${Math.random().toString(16).slice(2, 10).toUpperCase()}`
    return { steps: stepsFor(lang, ['loggingIntake']), text: T.foiaLogged(requestId), card: null }
  }

  return null
}

// ---------------------------------------------------------------------------
// Registry & runner
// ---------------------------------------------------------------------------
const RESOLVERS = {
  'citizen-inquiry': (msg, lang) => resolveCitizenInquiry(msg, lang),
  'benefits-eligibility': (msg, lang) => resolveBenefitsEligibility(msg, lang),
  'case-management': (msg, lang, context) => resolveCaseManagement(msg, lang, context),
  'permits-building': (msg, lang) => resolvePermits(msg, lang, 'building'),
  'permits-business': (msg, lang) => resolvePermits(msg, lang, 'business'),
  'tax-assistance': (msg, lang) => resolveTaxAssistance(msg, lang),
  'records-foia': (msg, lang) => resolveRecordsFoia(msg, lang),
}

function fallbackFor(agentKey, lang) {
  const T = TEXT[lang] || TEXT.en
  switch (agentKey) {
    case 'citizen-inquiry':
      return T.citizen.fallback
    case 'benefits-eligibility':
      return T.benefits.fallback
    case 'case-management':
      return T.case.fallback
    case 'permits-building':
      return T.permits.fallbackBuilding
    case 'permits-business':
      return T.permits.fallbackBusiness
    case 'tax-assistance':
      return T.tax.fallback
    case 'records-foia':
      return T.records.fallback
    default:
      return TEXT.en.citizen.fallback
  }
}

/**
 * Run a mock agent turn. Calls `onStep(label)` for each simulated
 * tool-execution step before resolving with the final `{ text, card }`.
 */
export async function runMockAgent({ agentKey, message, context = {}, lang = 'en', onStep }) {
  const resolver = RESOLVERS[agentKey]
  const resolved = resolver ? resolver(message, lang, context) : null
  const result = resolved || {
    steps: stepsFor(lang, ['thinking']),
    text: fallbackFor(agentKey, lang),
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
export async function runMockCardAction({ agentKey, actionId, lang = 'en', onStep }) {
  if (agentKey === 'tax-assistance' && actionId === 'PAY_ONLINE') {
    const result = resolveTaxPaymentSettlement(lang)
    for (const step of result.steps) {
      onStep?.(step)
      await delay(500 + Math.random() * 350)
    }
    await delay(250)
    return { text: result.text, card: result.card }
  }
  return { text: 'This action is not available in the demo.', card: null }
}
