import { useState, useRef, useEffect } from 'react'
import { useRouter } from 'next/router'

const QUESTIONS = [
  { id: 'Q1', text: "What's your email address?", type: 'text' },
  { id: 'Q2', text: "What's your current job title?", type: 'text' },
  { id: 'Q3', text: 'How many years of experience do you have?', type: 'number' },
  { id: 'Q4', text: "What's your current company?", type: 'text' },
  { id: 'Q5', text: 'Do you have a resume on file?', type: 'yes_no' },
  { id: 'Q6', text: 'Are you authorized to work in the US?', type: 'yes_no' },
  { id: 'Q7', text: 'Do you agree to be contacted about opportunities?', type: 'yes_no' },
  { id: 'Q8', text: 'I agree to the terms and conditions', type: 'yes_no' },
]

export default function ApplyPage() {
  const router = useRouter()
  const [messages, setMessages] = useState<Array<{ type: 'bot' | 'user', text: string }>>([
    { type: 'bot', text: "Hi! I'm here to learn about your background. We have a few quick questions." }
  ])
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0)
  const [responses, setResponses] = useState<Record<string, string>>({})
  const [inputValue, setInputValue] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    if (currentQuestionIndex === 0) {
      setMessages([{ type: 'bot', text: "Hi! I'm here to learn about your background. We have a few quick questions." }, { type: 'bot', text: QUESTIONS[0].text }])
    }
  }, [])

  const currentQuestion = QUESTIONS[currentQuestionIndex]
  const completionPercentage = Math.round(((currentQuestionIndex) / QUESTIONS.length) * 100)

  const handleSubmit = () => {
    if (!inputValue.trim()) return

    setResponses({ ...responses, [currentQuestion.id]: inputValue })
    setMessages([...messages, { type: 'user', text: inputValue }])
    setInputValue('')

    if (currentQuestionIndex < QUESTIONS.length - 1) {
      setTimeout(() => {
        setMessages(prev => [...prev, { type: 'bot', text: QUESTIONS[currentQuestionIndex + 1].text }])
        setCurrentQuestionIndex(currentQuestionIndex + 1)
      }, 500)
    } else {
      setMessages(prev => [...prev, { type: 'bot', text: '✅ Application submitted! We\'ll review your profile and get back to you soon.' }])
      setTimeout(() => router.push('/apply/status'), 2000)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div style={{ display: 'flex', height: '100vh', background: 'var(--surface-0)' }}>
      <div style={{ maxWidth: '600px', width: '100%', margin: '0 auto', background: 'var(--surface-1)', borderRadius: '12px', overflow: 'hidden', display: 'flex', flexDirection: 'column', boxShadow: '0 2px 8px rgba(0,0,0,0.1)' }}>
        <div style={{ background: 'linear-gradient(135deg, #185FA5 0%, #0C447C 100%)', color: 'white', padding: '1.5rem' }}>
          <h2 style={{ fontSize: '18px', fontWeight: 500, marginBottom: '0.25rem' }}>Business Delivery Consultant</h2>
          <p style={{ fontSize: '13px', opacity: 0.9 }}>Let's get to know you</p>
          <div style={{ marginTop: '1rem', height: '4px', background: 'rgba(255,255,255,0.3)', borderRadius: '2px', overflow: 'hidden' }}>
            <div style={{ height: '100%', background: 'white', width: `${completionPercentage}%`, transition: 'width 0.3s' }}></div>
          </div>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '12px', background: 'var(--surface-0)' }}>
          {messages.map((msg, i) => (
            <div key={i} style={{ display: 'flex', gap: '12px', justifyContent: msg.type === 'user' ? 'flex-end' : 'flex-start' }}>
              {msg.type === 'bot' && <div style={{ width: '36px', height: '36px', borderRadius: '50%', background: '#185FA5', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>🤖</div>}
              <div style={{
                maxWidth: '80%',
                padding: '12px 16px',
                borderRadius: '12px',
                fontSize: '14px',
                lineHeight: '1.5',
                background: msg.type === 'user' ? '#185FA5' : 'var(--surface-2)',
                color: msg.type === 'user' ? 'white' : 'var(--text-primary)',
                border: msg.type === 'bot' ? '0.5px solid var(--border)' : 'none'
              }}>
                {msg.text}
              </div>
              {msg.type === 'user' && <div style={{ width: '36px', height: '36px', borderRadius: '50%', background: '#85B7EB', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>😊</div>}
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        <div style={{ padding: '1rem 1.5rem', background: 'var(--surface-1)', borderTop: '0.5px solid var(--border)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', fontSize: '12px', color: 'var(--text-secondary)' }}>
            <span>Question {currentQuestionIndex + 1} of {QUESTIONS.length}</span>
            <span style={{ display: 'inline-block', background: '#E6F1FB', color: '#185FA5', padding: '4px 12px', borderRadius: 'var(--radius)', fontSize: '12px', fontWeight: 500 }}>{completionPercentage}% complete</span>
          </div>

          {currentQuestion?.type === 'yes_no' ? (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
              <button onClick={() => { setInputValue('yes'); setTimeout(() => handleSubmit(), 0) }} style={{ padding: '12px', border: '0.5px solid var(--border)', borderRadius: 'var(--radius)', background: 'var(--surface-2)', color: 'var(--text-primary)', cursor: 'pointer', fontSize: '14px', fontWeight: 500, transition: 'all 0.2s' }} onMouseEnter={(e) => { e.currentTarget.style.borderColor = '#185FA5'; e.currentTarget.style.background = 'rgba(24,95,165,0.05)' }} onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.background = 'var(--surface-2)' }}>Yes</button>
              <button onClick={() => { setInputValue('no'); setTimeout(() => handleSubmit(), 0) }} style={{ padding: '12px', border: '0.5px solid var(--border)', borderRadius: 'var(--radius)', background: 'var(--surface-2)', color: 'var(--text-primary)', cursor: 'pointer', fontSize: '14px', fontWeight: 500, transition: 'all 0.2s' }} onMouseEnter={(e) => { e.currentTarget.style.borderColor = '#185FA5'; e.currentTarget.style.background = 'rgba(24,95,165,0.05)' }} onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.background = 'var(--surface-2)' }}>No</button>
            </div>
          ) : (
            <div style={{ display: 'flex', gap: '8px' }}>
              <input
                type={currentQuestion?.type === 'number' ? 'number' : 'text'}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Type your answer..."
                autoFocus
                style={{ flex: 1, padding: '12px 16px', border: '0.5px solid var(--border)', borderRadius: 'var(--radius)', fontSize: '14px', fontFamily: 'inherit' }}
              />
              <button onClick={handleSubmit} style={{ padding: '12px 24px', background: '#185FA5', color: 'white', border: 'none', borderRadius: 'var(--radius)', cursor: 'pointer', fontWeight: 500, fontSize: '14px' }} onMouseEnter={(e) => e.currentTarget.style.background = '#0C447C'} onMouseLeave={(e) => e.currentTarget.style.background = '#185FA5'}>Next →</button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
