/**
 * Unified agent chat service. Every UI component calls through this file —
 * never the mock engine or fetch() directly — so switching between mock and
 * real backends is a single environment variable flip.
 */
import { runMockAgent, runMockCardAction } from '../mock/agentMocks'
import { AGENTS } from '../mock/departmentData'

const USE_MOCK = import.meta.env.VITE_USE_MOCK_AGENTS !== 'false'

const AGENT_URLS = Object.fromEntries(
  Object.values(AGENTS).map((agent) => [agent.key, `http://localhost:${agent.port}/chat`]),
)

/**
 * Send a chat message to an agent.
 *
 * @param {object} params
 * @param {string} params.agentKey - one of the keys in src/mock/departmentData.js AGENTS
 * @param {string} params.message
 * @param {string} params.sessionId
 * @param {string} [params.userId] - caseworker identity for OBO (X-User-ID header in real mode)
 * @param {object} [params.context] - extra context (e.g. { division: 'building' })
 * @param {(step: string) => void} [params.onStep] - called with each simulated tool-step label (mock mode only)
 * @returns {Promise<{ text: string, card: object|null }>}
 */
export async function sendAgentMessage({ agentKey, message, sessionId, userId, context = {}, onStep }) {
  if (USE_MOCK) {
    return runMockAgent({ agentKey, message, context: { ...context, userId }, onStep })
  }

  const url = AGENT_URLS[agentKey]
  if (!url) throw new Error(`Unknown agent: ${agentKey}`)

  const headers = { 'Content-Type': 'application/json' }
  if (userId) headers['X-User-ID'] = userId

  const res = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify({ message, session_id: sessionId, context }),
  })

  if (!res.ok) {
    throw new Error(`Agent request to ${agentKey} failed with status ${res.status}`)
  }

  const data = await res.json()
  return { text: data.response, card: null }
}

/**
 * Handle an interactive card action (e.g. "Pay Online"). Real-backend mode
 * has no direct equivalent yet — actions are demo-only until a dedicated
 * endpoint exists, so it degrades to a client-side notice.
 */
export async function sendCardAction({ agentKey, actionId, onStep }) {
  if (USE_MOCK) {
    return runMockCardAction({ agentKey, actionId, onStep })
  }
  return {
    text: 'Interactive actions are only available in mock mode in this demo build.',
    card: null,
  }
}

export const usingMockAgents = USE_MOCK
