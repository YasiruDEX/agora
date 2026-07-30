import { useEffect, useRef, useState } from 'react'
import { Send, X, MessageCircle, RefreshCw } from 'lucide-react'
import ChatMessage from './ChatMessage'
import DepartmentBadge from './DepartmentBadge'
import { AGENTS } from '../../mock/departmentData'
import { sendAgentMessage, sendCardAction, usingMockAgents } from '../../services/agentApi'

let idCounter = 0
const uid = () => `msg-${Date.now()}-${idCounter++}`

function TypingBubble({ steps }) {
  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] rounded-2xl rounded-bl-sm px-3.5 py-2.5 bg-white border border-slate-200 shadow-sm animate-gov-fade-in">
        {steps?.length > 0 && (
          <div className="mb-1.5 space-y-0.5">
            {steps.map((step, i) => (
              <p key={i} className="text-[11px] text-slate-400 italic flex items-center gap-1">
                <span className="inline-block w-1 h-1 rounded-full bg-slate-400" />
                {step}
              </p>
            ))}
          </div>
        )}
        <div className="flex items-center gap-1 h-4">
          <span className="w-1.5 h-1.5 rounded-full bg-slate-400 gov-typing-dot" style={{ animationDelay: '0ms' }} />
          <span className="w-1.5 h-1.5 rounded-full bg-slate-400 gov-typing-dot" style={{ animationDelay: '150ms' }} />
          <span className="w-1.5 h-1.5 rounded-full bg-slate-400 gov-typing-dot" style={{ animationDelay: '300ms' }} />
        </div>
      </div>
    </div>
  )
}

/**
 * @param {object} props
 * @param {string} props.agentKey - key into src/mock/departmentData.js AGENTS
 * @param {'floating'|'embedded'} [props.mode]
 * @param {string} [props.userId] - caseworker identity, for OBO-scoped agents
 * @param {object} [props.context] - extra context passed to the agent (e.g. { division: 'building' })
 * @param {string} [props.welcomeText] - override the default greeting
 * @param {boolean} [props.startOpen] - only applies to floating mode
 */
export default function ChatWidget({ agentKey, mode = 'floating', userId, context = {}, welcomeText, startOpen = false }) {
  const agent = AGENTS[agentKey]
  const sessionIdRef = useRef(`session-${agentKey}-${Date.now()}`)
  const scrollRef = useRef(null)

  const [open, setOpen] = useState(mode === 'embedded' || startOpen)
  const [messages, setMessages] = useState(() => [
    {
      id: uid(),
      role: 'agent',
      text: welcomeText || `Hello! I'm the ${agent?.name || 'Assistant'}. How can I help you today?`,
      card: null,
    },
  ])
  const [pending, setPending] = useState(null)
  const [actionLoadingId, setActionLoadingId] = useState(null)
  const [input, setInput] = useState('')
  const [checkout, setCheckout] = useState(null) // { messageId, actionId, card } | null

  // Reset the conversation whenever we switch to a different agent/persona
  // (e.g. toggling Benefits vs Case Management, or Joan vs Marcus).
  useEffect(() => {
    sessionIdRef.current = `session-${agentKey}-${userId || 'anon'}-${Date.now()}`
    setMessages([
      {
        id: uid(),
        role: 'agent',
        text: welcomeText || `Hello! I'm the ${agent?.name || 'Assistant'}. How can I help you today?`,
        card: null,
      },
    ])
    setPending(null)
    setActionLoadingId(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agentKey, userId])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, pending])

  if (!agent) {
    return <div className="text-sm text-maroon">Unknown agent: {agentKey}</div>
  }

  async function handleSend(text) {
    const trimmed = text.trim()
    if (!trimmed || pending) return

    setMessages((prev) => [...prev, { id: uid(), role: 'user', text: trimmed }])
    setInput('')
    setPending({ steps: [] })

    const result = await sendAgentMessage({
      agentKey,
      message: trimmed,
      sessionId: sessionIdRef.current,
      userId,
      context,
      onStep: (step) => setPending((prev) => ({ steps: [...(prev?.steps || []), step] })),
    })

    setMessages((prev) => [...prev, { id: uid(), role: 'agent', text: result.text, card: result.card }])
    setPending(null)
  }

  function handleCardActionRequest(messageId, actionId) {
    // Payment-style actions open a checkout modal first, rather than
    // executing immediately, to simulate a real municipal payment gateway
    // checkout step.
    if (actionId.startsWith('PAY_')) {
      const message = messages.find((m) => m.id === messageId)
      setCheckout({ messageId, actionId, card: message?.card })
      return
    }
    runCardAction(messageId, actionId)
  }

  async function runCardAction(messageId, actionId) {
    setActionLoadingId(messageId)
    setPending({ steps: [] })

    const result = await sendCardAction({
      agentKey,
      actionId,
      onStep: (step) => setPending((prev) => ({ steps: [...(prev?.steps || []), step] })),
    })

    setMessages((prev) => [
      ...prev.map((m) => (m.id === messageId ? { ...m, card: { ...m.card, actions: [] } } : m)),
      { id: uid(), role: 'agent', text: result.text, card: result.card },
    ])
    setPending(null)
    setActionLoadingId(null)
  }

  function confirmCheckout() {
    if (!checkout) return
    const { messageId, actionId } = checkout
    setCheckout(null)
    runCardAction(messageId, actionId)
  }

  function clearChat() {
    setMessages([
      {
        id: uid(),
        role: 'agent',
        text: welcomeText || `Hello! I'm the ${agent.name}. How can I help you today?`,
        card: null,
      },
    ])
    setPending(null)
  }

  const panel = (
    <div
      className={
        mode === 'floating'
          ? 'flex flex-col w-[min(23rem,calc(100vw-2rem))] h-[32rem] rounded-2xl overflow-hidden shadow-2xl border border-slate-200 bg-surface'
          : 'flex flex-col w-full h-[34rem] rounded-2xl overflow-hidden shadow-gov border border-slate-200 bg-surface'
      }
    >
      {/* Header */}
      <div className="bg-maroon px-3.5 py-3 flex items-center gap-2">
        <DepartmentBadge department={agent.department} agentName={agent.name} tier={agent.tier} />
        <div className="ml-auto flex items-center gap-1">
          <button
            onClick={clearChat}
            title="Clear chat"
            className="text-white/80 hover:text-white p-1.5 rounded hover:bg-white/10"
          >
            <RefreshCw className="w-3.5 h-3.5" strokeWidth={2} />
          </button>
          {mode === 'floating' && (
            <button
              onClick={() => setOpen(false)}
              title="Close"
              className="text-white/80 hover:text-white p-1.5 rounded hover:bg-white/10"
            >
              <X className="w-4 h-4" strokeWidth={2} />
            </button>
          )}
        </div>
      </div>

      {!usingMockAgents && (
        <div className="bg-gold-100 text-gold-800 text-[11px] text-center py-1">
          Live mode — sending real requests to localhost:{agent.port}
        </div>
      )}

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 py-3 space-y-3">
        {messages.map((m) => (
          <ChatMessage
            key={m.id}
            role={m.role}
            text={m.text}
            card={m.card}
            onAction={(actionId) => handleCardActionRequest(m.id, actionId)}
            actionLoading={actionLoadingId === m.id}
          />
        ))}
        {pending && <TypingBubble steps={pending.steps} />}
      </div>

      {/* Quick replies */}
      {agent.quickReplies?.length > 0 && (
        <div className="px-3 pt-1 pb-2 flex flex-wrap gap-1.5 border-t border-slate-200 bg-white">
          {agent.quickReplies.map((q) => (
            <button
              key={q}
              onClick={() => handleSend(q)}
              disabled={!!pending}
              className="text-[11px] font-medium bg-surface hover:bg-slate-100 border border-slate-300 text-slateink px-2.5 py-1 rounded-full disabled:opacity-50"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <form
        onSubmit={(e) => {
          e.preventDefault()
          handleSend(input)
        }}
        className="flex items-center gap-2 border-t border-slate-200 bg-white p-2.5"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your message..."
          disabled={!!pending}
          className="flex-1 text-sm rounded-full border border-slate-300 px-3.5 py-2 focus:outline-none focus:ring-2 focus:ring-gold focus:border-maroon disabled:bg-slate-100"
        />
        <button
          type="submit"
          disabled={!!pending || !input.trim()}
          className="w-9 h-9 shrink-0 rounded-full bg-maroon disabled:opacity-50 text-white flex items-center justify-center"
          aria-label="Send"
        >
          <Send className="w-4 h-4" strokeWidth={2} />
        </button>
      </form>
    </div>
  )

  const checkoutModal = checkout && (
    <div className="fixed inset-0 z-[60] bg-slateink/50 flex items-center justify-center p-4 animate-gov-fade-in">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-sm overflow-hidden">
        <div className="bg-maroon text-white px-4 py-3">
          <p className="font-bold text-sm">Municipal Portal Checkout</p>
          <p className="text-white/70 text-xs">Simulated payment gateway — no real transaction occurs</p>
        </div>
        <div className="p-4 space-y-1.5 text-sm">
          {checkout.card?.fields?.map((f) => (
            <div key={f.label} className="flex justify-between gap-3">
              <span className="text-slate-500">{f.label}</span>
              <span className="font-medium text-right">{f.value}</span>
            </div>
          ))}
        </div>
        <div className="px-4 pb-4 flex gap-2">
          <button
            onClick={() => setCheckout(null)}
            className="flex-1 border border-slate-300 text-slateink text-sm font-semibold py-2 rounded-full hover:bg-surface"
          >
            Cancel
          </button>
          <button
            onClick={confirmCheckout}
            className="flex-1 bg-gold hover:bg-gold-500 text-slateink text-sm font-bold py-2 rounded-full"
          >
            Confirm Payment
          </button>
        </div>
      </div>
    </div>
  )

  if (mode === 'embedded') {
    return (
      <>
        {panel}
        {checkoutModal}
      </>
    )
  }

  return (
    <div className="fixed bottom-5 right-5 z-50 flex flex-col items-end gap-3">
      {checkoutModal}
      {open && panel}
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-14 h-14 rounded-full bg-maroon text-white shadow-2xl flex items-center justify-center hover:bg-maroon-600 transition-colors"
        aria-label={open ? 'Close chat' : 'Open chat'}
      >
        {open ? (
          <X className="w-6 h-6" strokeWidth={2} />
        ) : (
          <MessageCircle className="w-6 h-6" strokeWidth={2} />
        )}
      </button>
    </div>
  )
}
