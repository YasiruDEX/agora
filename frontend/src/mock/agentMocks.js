/**
 * Mock agent engine. Simulates streaming tool-execution steps and a final
 * answer (with an optional structured "card" payload) for each of the 6
 * agent kinds, without requiring any backend to be running. Every string
 * shown to the user (steps, body text, card labels/status) is localized
 * across English / Sinhala / Tamil via the TEXT dictionary below.
 *
 * Note: the keyword matching below runs against the raw message text (which
 * is English in the built-in quick replies), regardless of UI language — the
 * *response* is localized, but recognizing "senior citizen allowance" etc.
 * in Sinhala/Tamil free text is out of scope for this demo engine.
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
  si: {
    searchingKb: 'දැනුම් සමුදාය සොයමින්...',
    consultingModel: 'ස්ථානීය සුදුසුකම් ආකෘතිය සමඟ සාකච්ඡා කරමින්...',
    applyingRules: 'ආදායම් සහ වයස පූර්ව-පරීක්ෂණ නීති යොදමින්...',
    reviewingPolicy: 'සුදුසුකම් ප්‍රතිපත්තිය සමාලෝචනය කරමින්...',
    queryingApplications: 'අයදුම්පත් වාර්තා විමසමින්...',
    lookingUpCase: 'නඩුව සොයමින්...',
    checkingObo: 'නඩු කළමනාකරු පැවරීම පරීක්ෂා කරමින් (OBO)...',
    retrievingNotes: 'නඩු සටහන් ලබාගනිමින්...',
    queryingPermitDb: 'බලපත්‍ර දත්ත සමුදාය විමසමින්...',
    checkingInspection: 'පරීක්ෂණ කාලසටහන පරීක්ෂා කරමින්...',
    checkingLedger: 'දේපළ ලෙජරය පරීක්ෂා කරමින්...',
    checkingDiscountWindow: 'කඩිනම් ගෙවීම් වට්ටම් කාලසීමාව පරීක්ෂා කරමින්...',
    calculatingAmount: 'අවසාන මුදල ගණනය කරමින්...',
    processingPayment: 'ගෙවීම සකසමින්...',
    verifyingBank: 'බැංකුව සමඟ තහවුරු කරමින් (අනුකරණය)...',
    generatingReceipt: 'ඩිජිටල් රිසිට්පත සකසමින්...',
    queryingRecordsRepo: 'වාර්තා ගබඩාව විමසමින්...',
    validatingExemption: 'නිදහස්කම තහවුරු කරමින්...',
    redactingPii: 'PII තොරතුරු ඉවත් කරමින්...',
    loggingIntake: 'ඉල්ලීම ලියාපදිංචි කරමින්...',
    thinking: 'සිතමින්...',
  },
  ta: {
    searchingKb: 'அறிவுத் தளத்தில் தேடுகிறது...',
    consultingModel: 'ஆன்-பிரெம் தகுதி மாதிரியுடன் ஆலோசிக்கிறது...',
    applyingRules: 'வருமானம் & வயது முன் திரையிடல் விதிகளைப் பயன்படுத்துகிறது...',
    reviewingPolicy: 'தகுதிக் கொள்கையை மறுஆய்வு செய்கிறது...',
    queryingApplications: 'விண்ணப்பப் பதிவுகளை வினவுகிறது...',
    lookingUpCase: 'வழக்கைத் தேடுகிறது...',
    checkingObo: 'வழக்கு மேலாளர் ஒதுக்கீட்டைச் சரிபார்க்கிறது (OBO)...',
    retrievingNotes: 'வழக்குக் குறிப்புகளை மீட்டெடுக்கிறது...',
    queryingPermitDb: 'அனுமதி தரவுத்தளத்தை வினவுகிறது...',
    checkingInspection: 'ஆய்வு அட்டவணையைச் சரிபார்க்கிறது...',
    checkingLedger: 'சொத்து லெட்ஜரைச் சரிபார்க்கிறது...',
    checkingDiscountWindow: 'விரைவு கட்டணத் தள்ளுபடி காலத்தைச் சரிபார்க்கிறது...',
    calculatingAmount: 'இறுதித் தொகையைக் கணக்கிடுகிறது...',
    processingPayment: 'கட்டணத்தைச் செயலாக்குகிறது...',
    verifyingBank: 'வங்கியுடன் சரிபார்க்கிறது (உருவகப்படுத்தப்பட்டது)...',
    generatingReceipt: 'டிஜிட்டல் ரசீதை உருவாக்குகிறது...',
    queryingRecordsRepo: 'பதிவுகள் களஞ்சியத்தை வினவுகிறது...',
    validatingExemption: 'விலக்கை சரிபார்க்கிறது...',
    redactingPii: 'PII-ஐ நீக்குகிறது...',
    loggingIntake: 'கோரிக்கையைப் பதிவு செய்கிறது...',
    thinking: 'சிந்திக்கிறது...',
  },
}

const TEXT = {
  en: {
    citizen: {
      officeHours:
        'The Municipal Council offices are open Monday through Friday from 8:30 AM to 4:15 PM. For urgent assistance, contact the Government Information Center at 1919.',
      birthDeathMarriage:
        'Birth, death, and marriage extracts are handled by the Department of Records & Compliance. Visit the Records & Compliance page to submit a request.',
      assessmentRoute:
        'Assessment rates are paid quarterly through the Tax & Revenue Department — at the Shroff Counter, or online via the Tax & Assessment Agent.',
      fallback:
        "I'm not certain about that yet in this demo — try asking about council working hours, assessment rate payments, or civil registration extracts.",
    },
    benefits: {
      eligible: (age, income) =>
        `Status: Eligible. Monthly Allowance: LKR 5,000. Based on age ${age} and monthly income LKR ${income.toLocaleString()}, you pre-qualify for the Senior Citizen Allowance. Final eligibility is confirmed after document verification.`,
      notEligible: (age, income) =>
        `Status: Not Eligible. Based on age ${age} and monthly income LKR ${income.toLocaleString()}, you do not currently meet the pre-screening thresholds (age 60+, income at or below LKR 15,000/month).`,
      askAgeIncome: 'To check your eligibility for the Senior Citizen Allowance, could you tell me your age and your monthly household income?',
      medicalAidDocs:
        'For medical low-income aid you will need: a completed Medical Assistance Application Form, a NIC copy, a Grama Niladhari income certificate, and supporting medical documents.',
      statusAskId: 'Please share your NIC or application ID so I can look up your benefits application status.',
      fallback:
        'I can help assess eligibility for the senior citizen allowance, medical low-income aid, or public assistance. Try asking about one of those.',
      cardTitle: 'Pre-Screening Result',
      statusEligible: 'ELIGIBLE',
      statusNotEligible: 'NOT ELIGIBLE',
      fields: { benefit: 'Benefit', monthlyAllowance: 'Monthly Allowance', age: 'Age', monthlyIncome: 'Monthly Income' },
      benefitName: 'Senior Citizen Allowance',
      allowanceAmount: 'LKR 5,000',
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
      notFound: (kind, nic) => `No ${kind} application found for NIC ${nic} in this division.`,
      statusLine: (appId, name, status) => `Application ${appId} for ${name} — Status: ${status}.`,
      buildingKind: 'building permit',
      tradeKind: 'trade license',
      cardTitleBuilding: 'Building Permit Application',
      cardTitleTrade: 'Trade License Application',
      fields: { applicationId: 'Application ID', applicant: 'Applicant', permitType: 'Permit Type', status: 'Status' },
      fallbackBuilding: 'Please provide a NIC number so I can check your Building Permit application status.',
      fallbackBusiness: 'Please provide a NIC number so I can check your Trade License application status.',
    },
    tax: {
      assessmentLine: (base, discountPct, net) =>
        `Property PROP-COL-2026-88 — Q1 assessment rate is LKR ${base.toLocaleString()}. A ${discountPct}% prompt payment discount applies, bringing your total to LKR ${net.toLocaleString()}.`,
      tradeTaxTiers:
        'Trade tax has three tiers: Tier A (small scale, LKR 1,000–5,000/yr), Tier B (medium scale, LKR 5,000–20,000/yr), and Tier C (large scale/corporate, LKR 20,000–50,000+/yr).',
      nonArrearsAsk: 'Please share your assessment number so I can check the non-arrears status for that property.',
      balanceAsk: 'Please share your assessment number (e.g. PROP-COL-2026-88) so I can look up your current balance.',
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
  si: {
    citizen: {
      officeHours:
        'නාගරික සභා කාර්යාල සඳුදා සිට සිකුරාදා දක්වා පෙ.ව. 8.30 සිට ප.ව. 4.15 දක්වා විවෘතව පවතී. හදිසි උපකාර සඳහා 1919 ඔස්සේ රජයේ තොරතුරු මධ්‍යස්ථානය අමතන්න.',
      birthDeathMarriage:
        'උප්පැන්න, මරණ සහ විවාහ සහතික උපුටා ගැනීම් වාර්තා හා අනුකූලතා දෙපාර්තමේන්තුව මගින් හසුරුවනු ලැබේ. ඉල්ලීමක් ඉදිරිපත් කිරීමට එම පිටුවට පිවිසෙන්න.',
      assessmentRoute:
        'තක්සේරු බදු කාර්තුමය වශයෙන් බදු හා ආදායම් දෙපාර්තමේන්තුව හරහා — ෂ්‍රොෆ් කවුන්ටරයේ හෝ තක්සේරු නියෝජිත ඔස්සේ අන්තර්ජාලයෙන් ගෙවිය හැක.',
      fallback:
        'මෙම නිරූපණයේ එයට තවම විශ්වාසයෙන් පිළිතුරු දිය නොහැක — සභා වැඩ කරන වේලාවන්, තක්සේරු බදු ගෙවීම් හෝ සිවිල් ලියාපදිංචි උපුටා ගැනීම් ගැන අසන්න.',
    },
    benefits: {
      eligible: (age, income) =>
        `තත්ත්වය: සුදුසුයි. මාසික දීමනාව: රු. 5,000. වයස ${age} සහ මාසික ආදායම රු. ${income.toLocaleString()} මත පදනම්ව, ඔබ වැඩිහිටි පුරවැසි දීමනාව සඳහා පූර්ව සුදුසුකම් ලබයි. ලේඛන සත්‍යාපනයෙන් පසු අවසන් සුදුසුකම තහවුරු කෙරේ.`,
      notEligible: (age, income) =>
        `තත්ත්වය: සුදුසු නොවේ. වයස ${age} සහ මාසික ආදායම රු. ${income.toLocaleString()} මත පදනම්ව, ඔබ දැනට පූර්ව-පරීක්ෂණ සීමාව සපුරාලන්නේ නැත (වයස 60+, ආදායම මසකට රු. 15,000 ට වඩා අඩු).`,
      askAgeIncome: 'වැඩිහිටි පුරවැසි දීමනාව සඳහා ඔබේ සුදුසුකම පරීක්ෂා කිරීමට, ඔබේ වයස සහ මාසික ගෘහ ආදායම කීයද?',
      medicalAidDocs:
        'වෛද්‍ය අඩු ආදායම් ආධාර සඳහා ඔබට අවශ්‍ය වන්නේ: සම්පූර්ණ කළ වෛද්‍ය ආධාර අයදුම්පත, ජාතික හැඳුනුම්පත් පිටපත, ග්‍රාම නිලධාරි ආදායම් සහතිකය සහ අනුබද්ධ වෛද්‍ය ලේඛන ය.',
      statusAskId: 'ඔබේ ජාතික හැඳුනුම්පත් අංකය හෝ අයදුම්පත් අංකය ලබාදෙන්න, එවිට මට ඔබේ දීමනා අයදුම්පත් තත්ත්වය පරීක්ෂා කළ හැක.',
      fallback: 'මට වැඩිහිටි පුරවැසි දීමනාව, වෛද්‍ය අඩු ආදායම් ආධාර, හෝ පොදු ආධාර සඳහා සුදුසුකම තක්සේරු කිරීමට හැකිය.',
      cardTitle: 'පූර්ව-පරීක්ෂණ ප්‍රතිඵලය',
      statusEligible: 'සුදුසුයි',
      statusNotEligible: 'සුදුසු නොවේ',
      fields: { benefit: 'ප්‍රතිලාභය', monthlyAllowance: 'මාසික දීමනාව', age: 'වයස', monthlyIncome: 'මාසික ආදායම' },
      benefitName: 'වැඩිහිටි පුරවැසි දීමනාව',
      allowanceAmount: 'රු. 5,000',
    },
    case: {
      noCase: (id) => `'${id}' අංකයේ නඩුවක් හමු නොවීය.`,
      accessDenied: (id, owner) =>
        `ආරක්ෂක නිවේදනය: ප්‍රවේශය ප්‍රතික්ෂේප විය. ${id} නඩුව ${owner} වෙත පවරා ඇති අතර, ඔබට නොවේ. ඔබට පවරා ඇති නඩු පමණක් නැරඹිය හැක.`,
      summary: (id, citizen, status) => `නඩුව ${id}: ${citizen} ගේ නඩුව දැනට ${status} තත්ත්වයේ පවතී.`,
      fallback: 'මට එය සොයාගැනීමට නඩු අංකයක් (උදා: CASE-2026-001) ලබාදෙන්න.',
      accessDeniedTitle: 'ප්‍රවේශය ප්‍රතික්ෂේප විය',
      caseTitlePrefix: 'නඩුව',
      statusDenied: 'ප්‍රතික්ෂේපිතයි',
      fields: { caseId: 'නඩු අංකය', assignedTo: 'පවරා ඇත්තේ', requestedBy: 'ඉල්ලූයේ', citizen: 'පුරවැසියා', caseType: 'නඩු වර්ගය', status: 'තත්ත්වය', notes: 'සටහන්' },
    },
    permits: {
      notFound: (kind, nic) => `මෙම අංශයේ ${nic} ජාතික හැඳුනුම්පත් අංකය සඳහා ${kind} අයදුම්පතක් හමු නොවීය.`,
      statusLine: (appId, name, status) => `${name} සඳහා ${appId} අයදුම්පත — තත්ත්වය: ${status}.`,
      buildingKind: 'ගොඩනැගිලි බලපත්‍ර',
      tradeKind: 'වෙළඳ බලපත්‍ර',
      cardTitleBuilding: 'ගොඩනැගිලි බලපත්‍ර අයදුම්පත',
      cardTitleTrade: 'වෙළඳ බලපත්‍ර අයදුම්පත',
      fields: { applicationId: 'අයදුම්පත් අංකය', applicant: 'අයදුම්කරු', permitType: 'බලපත්‍ර වර්ගය', status: 'තත්ත්වය' },
      fallbackBuilding: 'ඔබේ ගොඩනැගිලි බලපත්‍ර අයදුම්පත් තත්ත්වය පරීක්ෂා කිරීමට ජාතික හැඳුනුම්පත් අංකය ලබාදෙන්න.',
      fallbackBusiness: 'ඔබේ වෙළඳ බලපත්‍ර අයදුම්පත් තත්ත්වය පරීක්ෂා කිරීමට ජාතික හැඳුනුම්පත් අංකය ලබාදෙන්න.',
    },
    tax: {
      assessmentLine: (base, discountPct, net) =>
        `PROP-COL-2026-88 දේපළ — පළමු කාර්තුවේ තක්සේරු බදුව රු. ${base.toLocaleString()} කි. ${discountPct}% කඩිනම් ගෙවීම් වට්ටමක් අදාළ වන අතර, එමගින් ඔබේ මුළු මුදල රු. ${net.toLocaleString()} දක්වා අඩු වේ.`,
      tradeTaxTiers:
        'වෙළඳ බදුවේ ස්ථර තුනක් ඇත: A ස්ථරය (කුඩා පරිමාණ, වාර්ෂිකව රු. 1,000–5,000), B ස්ථරය (මධ්‍යම පරිමාණ, රු. 5,000–20,000), සහ C ස්ථරය (විශාල පරිමාණ/සංස්ථාපිත, රු. 20,000–50,000+).',
      nonArrearsAsk: 'එම දේපළෙහි නොපියවූ බදු තත්ත්වය පරීක්ෂා කිරීමට ඔබේ තක්සේරු අංකය ලබාදෙන්න.',
      balanceAsk: 'ඔබේ දැනට පවතින ශේෂය පරීක්ෂා කිරීමට ඔබේ තක්සේරු අංකය (උදා: PROP-COL-2026-88) ලබාදෙන්න.',
      fallback: 'මට තක්සේරු බදු ගෙවීම්, නොපියවූ බදු තත්ත්වය, හෝ වෙළඳ බදු ස්ථර පිළිබඳ උපකාර කළ හැක.',
      cardTitle: 'පළමු කාර්තුවේ තක්සේරු බදු ගෙවීම',
      payOnlineAction: 'අන්තර්ජාලයෙන් ගෙවන්න (නාගරික ද්වාරය)',
      statusPendingGateway: 'ගෙවීම අපේක්ෂිතයි',
      fields: { assessmentNo: 'තක්සේරු අංකය', baseAmount: 'මූලික මුදල', discount: 'කඩිනම් ගෙවීම් වට්ටම', netDue: 'ගෙවිය යුතු මුළු මුදල' },
      receiptText: 'ඔබේ ගෙවීම ලැබී පියවා ඇත. මෙන්න ඔබේ ඩිජිටල් රිසිට්පත.',
      receiptCardTitle: 'නාගරික බදු ගෙවීම් රිසිට්පත (අනුකරණය)',
      statusPaid: 'ගෙවා ඇත',
      receiptFields: { receiptNo: 'රිසිට්පත් අංකය', assessmentNo: 'තක්සේරු අංකය', period: 'කාලසීමාව', amountPaid: 'ගෙවූ මුදල', transactionId: 'ගනුදෙනු අංකය', status: 'තත්ත්වය' },
    },
    records: {
      notFound: (id) => `'${id}' අංකයේ පොදු වාර්තාවක් හමු නොවීය.`,
      exemptText: (reason) => `හෙළිදරව් කිරීම ප්‍රතික්ෂේප විය: ${reason}`,
      exemptionReason: 'ව්‍යවස්ථාපිත නිදහස්කම 7(A) - නීතිය ක්‍රියාත්මක කිරීමේ විමර්ශනයක් පවතී',
      disclosableText: (id, title, category) => `වාර්තාව ${id}: ${title} (ප්‍රවර්ගය: ${category})`,
      foiaLogged: (id) => `ඔබේ පොදු වාර්තා ඉල්ලීම ලියාපදිංචි කර ඇත. ඉල්ලීම් අංකය: ${id} (තත්ත්වය: ලැබී ඇත).`,
      fallback: 'වාර්තා අංකයක් (උදා: REC-2026-101) ලබාදෙන්න, නැතහොත් පොදු වාර්තා ඉල්ලීමක් ඉදිරිපත් කිරීමට කියන්න.',
      exemptCardTitlePrefix: 'වාර්තාව',
      statusExempt: 'නිදහස්',
      statusDisclosable: 'හෙළිදරව් කළ හැක',
      fields: { title: 'මාතෘකාව', category: 'ප්‍රවර්ගය', exemptionReason: 'නිදහස්කම් හේතුව', content: 'අන්තර්ගතය' },
      record101Title: '2025 නගර මධ්‍ය නඩත්තු ගිවිසුම',
      record101Content: 'කොන්ත්‍රාත්කරු: Apex Ltd. එකතුව: $450,000. සම්බන්ධතා: [PII ඉවත් කර ඇත], දුරකථනය: [PII ඉවත් කර ඇත]. හැඳුනුම් අංකය: [PII ඉවත් කර ඇත].',
      record102Title: 'දේපළ කලාප 4 පිළිබඳ අභ්‍යන්තර විමර්ශනය',
    },
  },
  ta: {
    citizen: {
      officeHours:
        'நகராட்சி அலுவலகங்கள் திங்கள் முதல் வெள்ளி வரை காலை 8.30 முதல் மாலை 4.15 வரை திறந்திருக்கும். அவசர உதவிக்கு 1919 எண்ணில் அரசாங்க தகவல் மையத்தை தொடர்பு கொள்ளவும்.',
      birthDeathMarriage:
        'பிறப்பு, இறப்பு, திருமணச் சான்றிதழ் பிரதிகள் பதிவுகள் & இணக்கத் திணைக்களத்தால் கையாளப்படுகின்றன. கோரிக்கையை சமர்ப்பிக்க அந்தப் பக்கத்திற்குச் செல்லவும்.',
      assessmentRoute:
        'மதிப்பீட்டு வரிகள் காலாண்டுதோறும் வரி & வருவாய்த் திணைக்களம் மூலம் — ஷ்ராஃப் கவுண்டரில் அல்லது வரி முகவர் மூலம் ஆன்லைனில் செலுத்தப்படும்.',
      fallback:
        'இந்த டெமோவில் அதற்கு இன்னும் உறுதியான பதில் இல்லை — சபை பணி நேரங்கள், மதிப்பீட்டு வரி கொடுப்பனவுகள் அல்லது சிவில் பதிவு பிரதிகள் பற்றி கேளுங்கள்.',
    },
    benefits: {
      eligible: (age, income) =>
        `நிலை: தகுதியானது. மாதாந்திர உதவித்தொகை: ரூ. 5,000. வயது ${age} மற்றும் மாத வருமானம் ரூ. ${income.toLocaleString()} அடிப்படையில், நீங்கள் முதியோர் உதவித்தொகைக்கு முன் தகுதி பெறுகிறீர்கள். ஆவணச் சரிபார்ப்புக்குப் பிறகு இறுதி தகுதி உறுதிப்படுத்தப்படும்.`,
      notEligible: (age, income) =>
        `நிலை: தகுதியற்றது. வயது ${age} மற்றும் மாத வருமானம் ரூ. ${income.toLocaleString()} அடிப்படையில், நீங்கள் தற்போது முன் திரையிடல் வரம்புகளை பூர்த்தி செய்யவில்லை (வயது 60+, வருமானம் மாதம் ரூ. 15,000 அல்லது அதற்கும் குறைவு).`,
      askAgeIncome: 'முதியோர் உதவித்தொகைக்கான உங்கள் தகுதியைச் சரிபார்க்க, உங்கள் வயது மற்றும் மாத வீட்டு வருமானத்தைச் சொல்ல முடியுமா?',
      medicalAidDocs:
        'மருத்துவ குறை வருமான உதவிக்கு உங்களுக்கு தேவை: பூர்த்தி செய்யப்பட்ட மருத்துவ உதவி விண்ணப்பப் படிவம், NIC பிரதி, கிராம சேவகர் வருமானச் சான்றிதழ் மற்றும் ஆதரவு மருத்துவ ஆவணங்கள்.',
      statusAskId: 'உங்கள் NIC அல்லது விண்ணப்ப எண்ணைப் பகிரவும், நான் உங்கள் சலுகை விண்ணப்ப நிலையைப் பார்க்கிறேன்.',
      fallback: 'முதியோர் உதவித்தொகை, மருத்துவ குறை வருமான உதவி, அல்லது பொது உதவி தகுதியை மதிப்பிட நான் உதவ முடியும்.',
      cardTitle: 'முன் திரையிடல் முடிவு',
      statusEligible: 'தகுதியானது',
      statusNotEligible: 'தகுதியற்றது',
      fields: { benefit: 'சலுகை', monthlyAllowance: 'மாதாந்திர உதவித்தொகை', age: 'வயது', monthlyIncome: 'மாத வருமானம்' },
      benefitName: 'முதியோர் உதவித்தொகை',
      allowanceAmount: 'ரூ. 5,000',
    },
    case: {
      noCase: (id) => `'${id}' எண்ணுடன் வழக்கு எதுவும் இல்லை.`,
      accessDenied: (id, owner) =>
        `பாதுகாப்பு அறிவிப்பு: அணுகல் மறுக்கப்பட்டது. வழக்கு ${id} உங்களுக்கு அல்ல, ${owner} க்கு ஒதுக்கப்பட்டுள்ளது. உங்கள் சொந்த பட்டியலில் ஒதுக்கப்பட்ட வழக்குகளை மட்டுமே நீங்கள் பார்க்க முடியும்.`,
      summary: (id, citizen, status) => `வழக்கு ${id}: ${citizen} இன் வழக்கு தற்போது ${status} நிலையில் உள்ளது.`,
      fallback: 'நான் தேட வழக்கு எண்ணை (எ.கா. CASE-2026-001) வழங்கவும்.',
      accessDeniedTitle: 'அணுகல் மறுக்கப்பட்டது',
      caseTitlePrefix: 'வழக்கு',
      statusDenied: 'மறுக்கப்பட்டது',
      fields: { caseId: 'வழக்கு எண்', assignedTo: 'ஒதுக்கப்பட்டவர்', requestedBy: 'கோரியவர்', citizen: 'குடிமகன்', caseType: 'வழக்கு வகை', status: 'நிலை', notes: 'குறிப்புகள்' },
    },
    permits: {
      notFound: (kind, nic) => `இந்த பிரிவில் NIC ${nic} க்கான ${kind} விண்ணப்பம் எதுவும் இல்லை.`,
      statusLine: (appId, name, status) => `${name} க்கான விண்ணப்பம் ${appId} — நிலை: ${status}.`,
      buildingKind: 'கட்டிட அனுமதி',
      tradeKind: 'வர்த்தக உரிமம்',
      cardTitleBuilding: 'கட்டிட அனுமதி விண்ணப்பம்',
      cardTitleTrade: 'வர்த்தக உரிம விண்ணப்பம்',
      fields: { applicationId: 'விண்ணப்ப எண்', applicant: 'விண்ணப்பதாரர்', permitType: 'அனுமதி வகை', status: 'நிலை' },
      fallbackBuilding: 'உங்கள் கட்டிட அனுமதி விண்ணப்ப நிலையைச் சரிபார்க்க NIC எண்ணை வழங்கவும்.',
      fallbackBusiness: 'உங்கள் வர்த்தக உரிம விண்ணப்ப நிலையைச் சரிபார்க்க NIC எண்ணை வழங்கவும்.',
    },
    tax: {
      assessmentLine: (base, discountPct, net) =>
        `சொத்து PROP-COL-2026-88 — முதல் காலாண்டு மதிப்பீட்டு வரி ரூ. ${base.toLocaleString()}. ${discountPct}% விரைவு கட்டணத் தள்ளுபடி பொருந்தும், இதனால் மொத்தம் ரூ. ${net.toLocaleString()} ஆகும்.`,
      tradeTaxTiers:
        'வர்த்தக வரியில் மூன்று அடுக்குகள் உள்ளன: அடுக்கு A (சிறிய அளவு, ஆண்டுக்கு ரூ. 1,000–5,000), அடுக்கு B (நடுத்தர அளவு, ரூ. 5,000–20,000), அடுக்கு C (பெரிய அளவு/பெருநிறுவனம், ரூ. 20,000–50,000+).',
      nonArrearsAsk: 'அந்த சொத்தின் நிலுவையில்லா நிலையைச் சரிபார்க்க உங்கள் மதிப்பீட்டு எண்ணை வழங்கவும்.',
      balanceAsk: 'உங்கள் தற்போதைய இருப்பைப் பார்க்க உங்கள் மதிப்பீட்டு எண்ணை (எ.கா. PROP-COL-2026-88) வழங்கவும்.',
      fallback: 'மதிப்பீட்டு வரி கொடுப்பனவுகள், நிலுவையில்லா நிலை, அல்லது வர்த்தக வரி அடுக்குகள் பற்றி நான் உதவ முடியும்.',
      cardTitle: 'முதல் காலாண்டு மதிப்பீட்டு வரி செலுத்துதல்',
      payOnlineAction: 'ஆன்லைனில் செலுத்து (நகராட்சி போர்டல்)',
      statusPendingGateway: 'கட்டணம் நிலுவையில்',
      fields: { assessmentNo: 'மதிப்பீட்டு எண்', baseAmount: 'அடிப்படைத் தொகை', discount: 'விரைவு கட்டணத் தள்ளுபடி', netDue: 'செலுத்த வேண்டிய மொத்தம்' },
      receiptText: 'உங்கள் கட்டணம் பெறப்பட்டு தீர்க்கப்பட்டது. இதோ உங்கள் டிஜிட்டல் ரசீது.',
      receiptCardTitle: 'நகராட்சி வரி கட்டண ரசீது (உருவகப்படுத்தப்பட்டது)',
      statusPaid: 'செலுத்தப்பட்டது',
      receiptFields: { receiptNo: 'ரசீது எண்', assessmentNo: 'மதிப்பீட்டு எண்', period: 'காலம்', amountPaid: 'செலுத்திய தொகை', transactionId: 'பரிவர்த்தனை எண்', status: 'நிலை' },
    },
    records: {
      notFound: (id) => `'${id}' எண்ணுடன் பொதுப் பதிவு எதுவும் இல்லை.`,
      exemptText: (reason) => `வெளியீடு மறுக்கப்பட்டது: ${reason}`,
      exemptionReason: 'சட்டப்பூர்வ விலக்கு 7(A) - சட்ட அமலாக்க விசாரணை நிலுவையில் உள்ளது',
      disclosableText: (id, title, category) => `பதிவு ${id}: ${title} (வகை: ${category})`,
      foiaLogged: (id) => `உங்கள் பொதுப் பதிவுக் கோரிக்கை பதிவு செய்யப்பட்டது. கோரிக்கை எண்: ${id} (நிலை: பெறப்பட்டது).`,
      fallback: 'பதிவு எண்ணை (எ.கா. REC-2026-101) வழங்கவும் அல்லது பொதுப் பதிவுக் கோரிக்கையைச் சமர்ப்பிக்கக் கேளுங்கள்.',
      exemptCardTitlePrefix: 'பதிவு',
      statusExempt: 'விலக்கு',
      statusDisclosable: 'வெளியிடக்கூடியது',
      fields: { title: 'தலைப்பு', category: 'வகை', exemptionReason: 'விலக்கு காரணம்', content: 'உள்ளடக்கம்' },
      record101Title: '2025 நகர மைய பராமரிப்பு ஒப்பந்தம்',
      record101Content: 'ஒப்பந்தக்காரர்: Apex Ltd. மொத்தம்: $450,000. தொடர்பு: [PII நீக்கப்பட்டது], தொலைபேசி: [PII நீக்கப்பட்டது]. SSN: [PII நீக்கப்பட்டது].',
      record102Title: 'சொத்து மண்டலம் 4 பற்றிய உள் விசாரணை',
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

  if (numbers.length >= 2 && (m.includes('year') || m.includes('income') || m.includes('earn') || m.includes('age') || m.includes('lkr'))) {
    const [age, income] = numbers
    const eligible = age >= 60 && income <= 15000
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
              { label: T.fields.monthlyIncome, value: `LKR ${income.toLocaleString()}` },
            ],
          }
        : {
            type: 'eligibility',
            title: T.cardTitle,
            status: T.statusNotEligible,
            badgeColor: 'maroon',
            fields: [
              { label: T.fields.age, value: String(age) },
              { label: T.fields.monthlyIncome, value: `LKR ${income.toLocaleString()}` },
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
    const base = 12500
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
          { label: T.fields.assessmentNo, value: 'PROP-COL-2026-88' },
          { label: T.fields.baseAmount, value: `LKR ${base.toLocaleString()}` },
          { label: T.fields.discount, value: `${discountPct}%` },
          { label: T.fields.netDue, value: `LKR ${net.toLocaleString()}` },
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
        { label: T.receiptFields.assessmentNo, value: 'PROP-COL-2026-88' },
        { label: T.receiptFields.period, value: 'Q1 2026' },
        { label: T.receiptFields.amountPaid, value: 'LKR 11,875.00' },
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
