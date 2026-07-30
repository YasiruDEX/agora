/**
 * Pool of illustrative Sri Lankan human-officer personas per agent kind.
 * Every new chat session is assigned one deterministically (hashed from the
 * session ID) so the same session always sees the same "officer", while
 * different sessions/visits see different ones. For the Case Management
 * agent the persona instead follows the active caseworker (Joan/Marcus),
 * since that identity drives the OBO access-control demo.
 */

export const OFFICER_POOLS = {
  'citizen-inquiry': [
    { id: 'selvarajah', name: 'T. Selvarajah', designationKey: 'informationOfficer' },
    { id: 'nizar-citizen', name: 'Farhana Nizar', designationKey: 'citizenServicesOfficer' },
    { id: 'jayasuriya', name: 'R. M. Jayasuriya', designationKey: 'contactCenterCoordinator' },
  ],
  'benefits-eligibility': [
    { id: 'wijesinghe', name: 'K. P. Wijesinghe', designationKey: 'socialServicesOfficer' },
    { id: 'fernando', name: 'Dilani Fernando', designationKey: 'welfareBenefitsOfficer' },
    { id: 'rajapaksha', name: 'S. Rajapaksha', designationKey: 'eligibilityAssessor' },
  ],
  'case-management': [
    { id: 'ellis', name: 'Joan Ellis', designationKey: 'seniorCaseworker' },
    { id: 'lee', name: 'Marcus Lee', designationKey: 'caseworker' },
  ],
  'permits-building': [
    { id: 'gunasekera', name: 'A. B. Gunasekera', designationKey: 'buildingInspector' },
    { id: 'de-silva', name: 'Chaminda de Silva', designationKey: 'permitsOfficer' },
  ],
  'permits-business': [
    { id: 'wickramasinghe', name: 'N. Wickramasinghe', designationKey: 'licensingOfficer' },
    { id: 'perera-b', name: 'Buddhika Perera', designationKey: 'tradeLicenseOfficer' },
  ],
  'tax-assistance': [
    { id: 'perera-kl', name: 'K. L. Perera', designationKey: 'seniorRevenueInspector' },
    { id: 'nizar-tax', name: 'Farhana Nizar', designationKey: 'assessmentOfficer' },
    { id: 'bandara', name: 'M. Bandara', designationKey: 'revenueCollector' },
  ],
  'records-foia': [
    { id: 'selvarajah-records', name: 'T. Selvarajah', designationKey: 'informationOfficer' },
    { id: 'jayawardena', name: 'S. Jayawardena', designationKey: 'recordsComplianceOfficer' },
  ],
}

function hashString(str) {
  let h = 0
  for (let i = 0; i < str.length; i++) {
    h = (h * 31 + str.charCodeAt(i)) | 0
  }
  return Math.abs(h)
}

export function assignOfficer(agentKey, sessionId, userId) {
  const pool = OFFICER_POOLS[agentKey] || OFFICER_POOLS['citizen-inquiry']

  if (agentKey === 'case-management') {
    const wanted = userId === 'marcus.lee' ? 'lee' : 'ellis'
    return pool.find((p) => p.id === wanted) || pool[0]
  }

  const idx = hashString(sessionId || '') % pool.length
  return pool[idx]
}
