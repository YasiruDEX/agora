/**
 * Pool of illustrative Riverside County human-officer personas per agent kind.
 * Every new chat session is assigned one deterministically (hashed from the
 * session ID) so the same session always sees the same "officer", while
 * different sessions/visits see different ones. For the Case Management
 * agent the persona instead follows the active caseworker (Joan/Marcus),
 * since that identity drives the OBO access-control demo.
 */

export const OFFICER_POOLS = {
  'citizen-inquiry': [
    { id: 'thompson', name: 'T. Thompson', designationKey: 'informationOfficer' },
    { id: 'nguyen-citizen', name: 'Farrah Nguyen', designationKey: 'citizenServicesOfficer' },
    { id: 'reyes', name: 'R. M. Reyes', designationKey: 'contactCenterCoordinator' },
  ],
  'benefits-eligibility': [
    { id: 'kingston', name: 'K. P. Kingston', designationKey: 'socialServicesOfficer' },
    { id: 'delgado', name: 'Dana Delgado', designationKey: 'welfareBenefitsOfficer' },
    { id: 'ramirez', name: 'S. Ramirez', designationKey: 'eligibilityAssessor' },
  ],
  'case-management': [
    { id: 'ellis', name: 'Joan Ellis', designationKey: 'seniorCaseworker' },
    { id: 'lee', name: 'Marcus Lee', designationKey: 'caseworker' },
  ],
  'permits-building': [
    { id: 'hayes', name: 'A. B. Hayes', designationKey: 'buildingInspector' },
    { id: 'de-silva', name: 'Chad de Silva', designationKey: 'permitsOfficer' },
  ],
  'permits-business': [
    { id: 'winters', name: 'N. Winters', designationKey: 'licensingOfficer' },
    { id: 'porter-b', name: 'Bradley Porter', designationKey: 'tradeLicenseOfficer' },
  ],
  'tax-assistance': [
    { id: 'porter-kl', name: 'K. L. Porter', designationKey: 'seniorRevenueInspector' },
    { id: 'nguyen-tax', name: 'Farrah Nguyen', designationKey: 'assessmentOfficer' },
    { id: 'bandera', name: 'M. Bandera', designationKey: 'revenueCollector' },
  ],
  'records-foia': [
    { id: 'thompson-records', name: 'T. Thompson', designationKey: 'informationOfficer' },
    { id: 'jennings', name: 'S. Jennings', designationKey: 'recordsComplianceOfficer' },
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
