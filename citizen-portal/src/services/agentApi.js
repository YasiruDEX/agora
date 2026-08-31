/**
 * Unified agent chat service. Every UI component calls through this file —
 * never the mock engine or fetch() directly — so switching a given agent
 * between mock and a real Agent Manager-fronted backend is a config change,
 * not a code change.
 *
 * Real backends are configured per agent key via env vars:
 *   VITE_AGENT_<KEY>_URL      — the agent's Agent Manager invoke URL (no trailing /chat)
 *   VITE_AGENT_<KEY>_API_KEY  — the API key shown on that agent's Overview page
 * where <KEY> is the agentKey from src/mock/departmentData.js AGENTS, dashes -> underscores,
 * uppercased (e.g. 'citizen-inquiry-social-services' -> VITE_AGENT_CITIZEN_INQUIRY_SOCIAL_SERVICES_URL).
 *
 * An agent with no configured URL/API key (or a placeholder value starting with
 * REPLACE_WITH) automatically falls back to the scripted mock engine — so partially
 * configuring only a few real agents is safe and expected.
 */
import { runMockAgent, runMockCardAction } from '../mock/agentMocks'

function envKeyFor(agentKey, suffix) {
  return `VITE_AGENT_${agentKey.replace(/-/g, '_').toUpperCase()}_${suffix}`
}

function isConfigured(value) {
  return typeof value === 'string' && value.length > 0 && !value.startsWith('REPLACE_WITH')
}

/** @returns {{url: string, apiKey: string}|null} */
export function getAgentEndpoint(agentKey) {
  const url = import.meta.env[envKeyFor(agentKey, 'URL')]
  const apiKey = import.meta.env[envKeyFor(agentKey, 'API_KEY')]
  if (!isConfigured(url) || !isConfigured(apiKey)) return null
  return { url, apiKey }
}

export function isAgentReal(agentKey) {
  return getAgentEndpoint(agentKey) !== null
}

/**
 * Send a chat message to an agent.
 *
 * @param {object} params
 * @param {string} params.agentKey - one of the keys in src/mock/departmentData.js AGENTS
 * @param {string} params.message
 * @param {string} params.sessionId
 * @param {string} [params.userId] - caseworker identity for OBO (sent as X-OBO-Token in real mode)
 * @param {object} [params.context] - extra context (e.g. { division: 'building' })
 * @param {string} [params.lang] - active UI language, mock mode only
 * @param {(step: string) => void} [params.onStep] - simulated tool-step callback, mock mode only
 * @returns {Promise<{ text: string, card: object|null }>}
 */
export async function sendAgentMessage({ agentKey, message, sessionId, userId, context = {}, lang = 'en', onStep }) {
  const endpoint = getAgentEndpoint(agentKey)
  if (!endpoint) {
    return runMockAgent({ agentKey, message, context: { ...context, userId }, lang, onStep })
  }

  const headers = {
    Accept: 'application/json',
    'Content-Type': 'application/json',
    'X-API-Key': endpoint.apiKey,
  }
  // On-behalf-of caseworker identity, for agents that scope by it (e.g. Case Management).
  if (userId) headers['X-OBO-Token'] = userId

  const res = await fetch(`${endpoint.url.replace(/\/$/, '')}/chat`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ message, session_id: sessionId, context }),
  })

  if (!res.ok) {
    let detail = ''
    try {
      const body = await res.json()
      detail = body?.message || body?.error || ''
    } catch {
      // response wasn't JSON — leave detail empty
    }
    throw new Error(`Agent request to ${agentKey} failed with status ${res.status}${detail ? `: ${detail}` : ''}`)
  }

  const data = await res.json()
  return { text: data.response, card: null }
}

/**
 * Handle an interactive card action (e.g. "Pay Online"). Real-backend mode
 * has no direct equivalent yet — actions are demo-only until a dedicated
 * endpoint exists, so it degrades to a client-side notice.
 */
export async function sendCardAction({ agentKey, actionId, lang = 'en', onStep }) {
  if (!isAgentReal(agentKey)) {
    return runMockCardAction({ agentKey, actionId, lang, onStep })
  }
  return {
    text: 'Interactive actions are only available in demo mode in this build.',
    card: null,
  }
}
