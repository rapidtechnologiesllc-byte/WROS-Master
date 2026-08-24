import { useState, useRef, useEffect } from 'react'
import { useRouter } from 'next/router'
import axios from 'axios'

interface Message {
  type: 'bot' | 'user'
  text: string
}

interface ResumeAnalysis {
  overall_fit_score: number
  gaps_identified: any[]
  has_critical_gaps: boolean
  tags: string[]
}

interface AuthState {
  email: string
  name: string
  password: string
  role: string
}

export default function ApplyV2Page() {
  const router = useRouter()
  const jobId = router.query.jobId as string

  const [stage, setStage] = useState<'auth' | 'welcome-back' | 'relationship' | 'resume' | 'analysis' | 'clarifications' | 'complete'>('auth')
  const [authMode, setAuthMode] = useState<'guest' | 'login' | 'signup'>('guest')
  const [authState, setAuthState] = useState<AuthState>({ email: '', name: '', password: '', role: 'consultant' })
  const [authError, setAuthError] = useState('')
  const [authLoading, setAuthLoading] = useState(false)
  const [candidateEmail, setCandidateEmail] = useState('')
  const [candidateName, setCandidateName] = useState('')

  const [returningCandidate, setReturningCandidate] = useState<any>(null)
  const [loadingReturning, setLoadingReturning] = useState(false)

  // Dynamic chat state
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState('')
  const [showJobContext, setShowJobContext] = useState(false)
  const [thinking, setThinking] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Conversation tracking
  const [conversationResponses, setConversationResponses] = useState<Record<string, string>>({})
  const [conversationStage, setConversationStage] = useState(0)

  // Resume stage
  const [resumeFile, setResumeFile] = useState<File | null>(null)
  const [resumeText, setResumeText] = useState('')
  const [uploading, setUploading] = useState(false)

  // Analysis stage
  const [analysis, setAnalysis] = useState<ResumeAnalysis | null>(null)
  const [analyzing, setAnalyzing] = useState(false)

  // Clarifications stage
  const [clarifications, setClarifications] = useState<any[]>([])
  const [clarificationResponses, setClarificationResponses] = useState<Record<string, string>>({})
  const [currentClarificationIndex, setCurrentClarificationIndex] = useState(0)

  const jobDetails = {
    title: 'Business Delivery Consultant',
    company: 'BlitzenX',
    location: 'San Francisco, CA',
    type: 'Full-time',
    experience: '5+ years',
    description: 'Lead customer implementations and drive business outcomes.',
    skills: ['Project Management', 'Client Relations', 'Guidewire', 'Business Analysis']
  }

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // Initialize conversation with first question
  useEffect(() => {
    if (stage === 'relationship' && messages.length === 0) {
      const initialMessage = {
        type: 'bot' as const,
        text: "Hey! I'm ⚡ Thunder, your AI career assistant. I'd love to get to know you better before we dive into your resume. What's your background?"
      }
      setMessages([initialMessage])
    }
  }, [stage])

  const checkReturningCandidate = async (email: string) => {
    try {
      setLoadingReturning(true)
      const response = await axios.post('http://localhost:8080/api/v1/candidates/check-returning', { email })
      if (response.data.isReturning) {
        return response.data
      }
      return null
    } catch (error) {
      console.error('Error checking returning candidate:', error)
      return null
    } finally {
      setLoadingReturning(false)
    }
  }

  // AUTH HANDLERS
  const handleGuestSubmit = async () => {
    if (!authState.email.trim()) return

    setCandidateEmail(authState.email)
    setLoadingReturning(true)
    const returningData = await checkReturningCandidate(authState.email)
    setLoadingReturning(false)

    if (returningData) {
      setReturningCandidate(returningData)
      setStage('welcome-back')
    } else {
      localStorage.setItem('candidateData', JSON.stringify({ email: authState.email, isGuest: true }))
      setStage('relationship')
    }
  }

  const handleLoginSubmit = async () => {
    if (!authState.email.trim() || !authState.password.trim()) return
    setAuthLoading(true)
    setAuthError('')
    try {
      setCandidateEmail(authState.email)
      localStorage.setItem('candidateData', JSON.stringify({ email: authState.email, name: authState.name, isGuest: false }))
      setStage('relationship')
    } catch (error) {
      setAuthError('Invalid email or password')
    } finally {
      setAuthLoading(false)
    }
  }

  const handleSignupSubmit = async () => {
    if (!authState.email.trim() || !authState.password.trim() || !authState.name.trim()) return
    if (authState.password.length < 8) {
      setAuthError('Password must be at least 8 characters')
      return
    }
    setAuthLoading(true)
    setAuthError('')
    try {
      setCandidateEmail(authState.email)
      setCandidateName(authState.name)
      localStorage.setItem('candidateData', JSON.stringify({
        email: authState.email,
        name: authState.name,
        role: authState.role,
        isGuest: false
      }))
      setStage('relationship')
    } catch (error) {
      setAuthError('Failed to create account')
    } finally {
      setAuthLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (stage === 'auth' && authMode === 'guest') {
        handleGuestSubmit()
      } else if (stage === 'auth' && authMode === 'login') {
        handleLoginSubmit()
      } else if (stage === 'auth' && authMode === 'signup') {
        handleSignupSubmit()
      } else if ((stage === 'relationship' || stage === 'analysis') && !thinking) {
        handleAskThunder()
      }
    }
  }

  // ASK THUNDER - Main interaction
  const handleAskThunder = async () => {
    if (!inputValue.trim() || thinking) return

    setThinking(true)
    const userMessage: Message = { type: 'user', text: inputValue }
    setMessages([...messages, userMessage])

    const responseIndex = conversationStage
    setConversationResponses({
      ...conversationResponses,
      [responseIndex]: inputValue
    })
    setInputValue('')

    // Simulate Thunder thinking
    await new Promise(resolve => setTimeout(resolve, 1200))

    // Generate contextual follow-up or transition
    let botResponse = ''

    if (responseIndex === 0) {
      botResponse = "That sounds great! How many years of experience do you have in this field?"
    } else if (responseIndex === 1) {
      botResponse = "Nice! What are your top 3 skills that make you stand out?"
    } else if (responseIndex === 2) {
      botResponse = "Impressive skills. Why are you interested in this Delivery Consultant role specifically?"
    } else if (responseIndex === 3) {
      botResponse = "I love the enthusiasm! What does your ideal next opportunity look like?"
    } else if (responseIndex === 4) {
      botResponse = "Perfect! Now let me analyze how you match this role. Upload your resume so I can assess the fit and identify any growth areas."
      // Save conversation and move to resume
      setTimeout(() => {
        saveConversationAndMoveToResume()
      }, 1500)
      setMessages(prev => [...prev, { type: 'bot', text: botResponse }])
      setThinking(false)
      return
    }

    setConversationStage(responseIndex + 1)
    setMessages(prev => [...prev, { type: 'bot', text: botResponse }])
    setThinking(false)
  }

  const saveConversationAndMoveToResume = async () => {
    try {
      await axios.post('http://localhost:8080/api/v1/careers/conversations/save', {
        candidate_email: candidateEmail,
        job_id: jobId || 'default',
        candidate_name: candidateName || candidateEmail.split('@')[0],
        responses: conversationResponses
      })
    } catch (error) {
      console.error('Failed to save conversation:', error)
    }
    setStage('resume')
  }

  // RESUME HANDLERS
  const handleResumeSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      setResumeFile(file)
      const reader = new FileReader()
      reader.onload = (event) => {
        setResumeText(event.target?.result as string)
      }
      reader.readAsText(file)
    }
  }

  const handleResumeUpload = async () => {
    if (!resumeFile || !resumeText) {
      alert('Please select a resume file')
      return
    }

    setUploading(true)
    setAnalyzing(true)
    try {
      const analysisResponse = await axios.post('http://localhost:8080/api/v1/careers/analyze-resume', {
        resume_text: resumeText,
        job_id: jobId || 'default',
        email: candidateEmail
      })

      setAnalysis(analysisResponse.data)

      if (analysisResponse.data.gaps_identified && analysisResponse.data.gaps_identified.length > 0) {
        const clarificationResponse = await axios.post('http://localhost:8080/api/v1/careers/clarifications/generate', {
          gaps: analysisResponse.data.gaps_identified,
          resume_text: resumeText,
          job_id: jobId || 'default'
        })
        setClarifications(clarificationResponse.data.clarifications || [])
        setMessages([{ type: 'bot', text: `Great resume! I found a fit score of ${Math.round(analysisResponse.data.overall_fit_score)}%. I have a few quick questions to understand your experience better.` }])
        setStage('analysis')
      } else {
        setMessages([{ type: 'bot', text: 'Perfect match! Your resume aligns well with this role. Submitting your application now.' }])
        setStage('complete')
      }
    } catch (error) {
      console.error('Resume analysis failed:', error)
      setAnalysis({
        overall_fit_score: 82,
        gaps_identified: [
          { gap_type: 'experience', description: 'JD requires 5 years, resume shows 3 years' }
        ],
        has_critical_gaps: false,
        tags: ['Project Management', 'Client Relations']
      })
      setMessages([{ type: 'bot', text: 'Analysis complete. Let me clarify a few points about your background.' }])
      setStage('analysis')
    } finally {
      setUploading(false)
      setAnalyzing(false)
    }
  }

  // CLARIFICATIONS HANDLERS
  const handleClarificationSubmit = () => {
    if (!inputValue.trim()) return

    const userMessage: Message = { type: 'user', text: inputValue }
    setMessages([...messages, userMessage])

    const current = clarifications[currentClarificationIndex]
    setClarificationResponses({ ...clarificationResponses, [current.id]: inputValue })
    setInputValue('')

    if (currentClarificationIndex < clarifications.length - 1) {
      setCurrentClarificationIndex(currentClarificationIndex + 1)
      setTimeout(() => {
        setMessages(prev => [...prev, { type: 'bot', text: clarifications[currentClarificationIndex + 1].ai_question }])
      }, 800)
    } else {
      submitApplication()
    }
  }

  const submitApplication = async () => {
    try {
      const applicationData = {
        career_job_id: jobId || 'default',
        candidate_email: candidateEmail,
        candidate_name: candidateName || candidateEmail.split('@')[0],
        resume_text: resumeText,
        analysis: analysis,
        clarifications: clarificationResponses,
        conversation_responses: conversationResponses
      }

      await axios.post('http://localhost:8080/api/v1/careers/applications', applicationData)

      // Store candidate email for dashboard access
      localStorage.setItem('candidateEmail', candidateEmail)
      localStorage.setItem('candidateName', candidateName || candidateEmail.split('@')[0])

      setMessages(prev => [...prev, { type: 'bot', text: '🎉 Your application is submitted! We\'ll review and get back to you within 3 business days.' }])
      setStage('complete')
    } catch (error) {
      console.error('Failed to submit application:', error)
      // Still store email even if submission fails, so they can check status
      localStorage.setItem('candidateEmail', candidateEmail)
      localStorage.setItem('candidateName', candidateName || candidateEmail.split('@')[0])
      setStage('complete')
    }
  }

  // HEADER
  const Header = () => (
    <nav style={{ background: 'linear-gradient(135deg, #0B1F3A 0%, #1a2d3f 100%)', borderBottom: '2px solid #F58220', padding: '1rem 2rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <a href="/jobs" style={{ color: '#F58220', fontSize: '18px', fontWeight: 700, textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        ⚡ BlitzenX
      </a>
      {stage !== 'auth' && (
        <button
          onClick={() => router.push('/jobs')}
          style={{ padding: '8px 16px', background: 'transparent', color: '#F58220', border: '1px solid #F58220', borderRadius: '6px', fontSize: '13px', fontWeight: 600, cursor: 'pointer' }}
        >
          ← Back to Jobs
        </button>
      )}
    </nav>
  )

  // ============ RENDER STAGES ============

  // AUTH STAGE
  if (stage === 'auth') {
    return (
      <div style={{ display: 'flex', height: '100vh', background: 'linear-gradient(135deg, #0B1F3A 0%, #1a2d3f 50%, #2E3A4D 100%)', alignItems: 'center', justifyContent: 'center', position: 'relative', overflow: 'hidden' }}>
        <style>{`
          @keyframes float { 0%, 100% { transform: translateY(0px); } 50% { transform: translateY(20px); } }
          .auth-bg { position: absolute; border-radius: 50%; opacity: 0.08; }
          .auth-bg-1 { width: 400px; height: 400px; top: -100px; left: -100px; background: #F58220; animation: float 8s ease-in-out infinite; }
          .auth-bg-2 { width: 300px; height: 300px; bottom: -50px; right: -50px; background: #D96E14; animation: float 6s ease-in-out infinite 1s; }
        `}</style>
        <div className="auth-bg auth-bg-1"></div>
        <div className="auth-bg auth-bg-2"></div>

        <div style={{ maxWidth: '420px', width: '100%', background: 'rgba(255, 255, 255, 0.98)', borderRadius: '16px', padding: '2rem', boxShadow: '0 20px 60px rgba(0, 0, 0, 0.3)', position: 'relative', zIndex: 1, backdropFilter: 'blur(10px)' }}>
          <div style={{ marginBottom: '1.5rem', textAlign: 'center' }}>
            <div style={{ fontSize: '48px', marginBottom: '0.75rem', animation: 'float 3s ease-in-out infinite' }}>⚡</div>
            <h1 style={{ fontSize: '24px', fontWeight: 700, background: 'linear-gradient(135deg, #0B1F3A 0%, #F58220 100%)', backgroundClip: 'text', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', margin: 0, marginBottom: '0.25rem' }}>
              Meet Thunder
            </h1>
            <p style={{ fontSize: '14px', color: '#666666', marginBottom: 0, fontWeight: 500 }}>Your AI Career Assistant</p>
          </div>

          {authError && <div style={{ background: '#FFEBEE', color: '#C62828', padding: '12px', borderRadius: '8px', fontSize: '13px', marginBottom: '1rem', border: '1px solid #EF5350' }}>{authError}</div>}

          <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem', borderBottom: '2px solid #E0E0E0' }}>
            {(['guest', 'login', 'signup'] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => { setAuthMode(mode); setAuthError(''); setAuthState({ email: '', name: '', password: '', role: 'consultant' }) }}
                style={{ flex: 1, padding: '12px', background: authMode === mode ? 'linear-gradient(135deg, #F58220 0%, #D96E14 100%)' : 'transparent', color: authMode === mode ? 'white' : '#666666', border: 'none', fontSize: '13px', fontWeight: 600, cursor: 'pointer', textTransform: 'capitalize', borderRadius: '6px', transition: 'all 0.3s' }}
              >
                {mode === 'guest' ? '⚡ Quick Start' : mode === 'login' ? '🔑 Sign In' : '✨ Join'}
              </button>
            ))}
          </div>

          {authMode === 'guest' && (
            <div>
              <div style={{ marginBottom: '1.5rem' }}>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#F58220', marginBottom: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Your Email</label>
                <input
                  type="email"
                  value={authState.email}
                  onChange={(e) => setAuthState({ ...authState, email: e.target.value })}
                  onKeyPress={handleKeyPress}
                  placeholder="you@example.com"
                  autoFocus
                  style={{ width: '100%', padding: '14px 16px', border: '2px solid #E0E0E0', borderRadius: '10px', fontSize: '14px', boxSizing: 'border-box', outline: 'none', transition: 'all 0.3s' }}
                  onFocus={(e) => { e.currentTarget.style.borderColor = '#F58220'; e.currentTarget.style.boxShadow = '0 0 0 3px rgba(245, 130, 32, 0.1)' }}
                  onBlur={(e) => { e.currentTarget.style.borderColor = '#E0E0E0'; e.currentTarget.style.boxShadow = 'none' }}
                />
              </div>
              <button
                onClick={handleGuestSubmit}
                disabled={!authState.email.trim() || loadingReturning}
                style={{ width: '100%', padding: '14px', background: authState.email.trim() ? 'linear-gradient(135deg, #F58220 0%, #D96E14 100%)' : '#E0E0E0', color: 'white', border: 'none', borderRadius: '10px', fontSize: '15px', fontWeight: 700, cursor: authState.email.trim() ? 'pointer' : 'not-allowed', boxShadow: authState.email.trim() ? '0 4px 15px rgba(245, 130, 32, 0.3)' : 'none', transition: 'all 0.3s' }}
                onMouseEnter={(e) => { if (authState.email.trim()) e.currentTarget.style.transform = 'translateY(-2px)' }}
                onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)' }}
              >
                {loadingReturning ? '🔄 Checking...' : '⚡ Start Conversation →'}
              </button>
            </div>
          )}

          {authMode === 'login' && (
            <div>
              <div style={{ marginBottom: '1.5rem' }}>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#F58220', marginBottom: '0.75rem', textTransform: 'uppercase' }}>Email</label>
                <input
                  type="email"
                  value={authState.email}
                  onChange={(e) => setAuthState({ ...authState, email: e.target.value })}
                  placeholder="you@example.com"
                  autoFocus
                  style={{ width: '100%', padding: '14px 16px', border: '2px solid #E0E0E0', borderRadius: '10px', fontSize: '14px', boxSizing: 'border-box', outline: 'none' }}
                  onFocus={(e) => e.currentTarget.style.borderColor = '#F58220'}
                  onBlur={(e) => e.currentTarget.style.borderColor = '#E0E0E0'}
                />
              </div>
              <div style={{ marginBottom: '1.5rem' }}>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#F58220', marginBottom: '0.75rem', textTransform: 'uppercase' }}>Password</label>
                <input
                  type="password"
                  value={authState.password}
                  onChange={(e) => setAuthState({ ...authState, password: e.target.value })}
                  onKeyPress={handleKeyPress}
                  placeholder="••••••••"
                  style={{ width: '100%', padding: '14px 16px', border: '2px solid #E0E0E0', borderRadius: '10px', fontSize: '14px', boxSizing: 'border-box', outline: 'none' }}
                />
              </div>
              <button
                onClick={handleLoginSubmit}
                disabled={!authState.email.trim() || !authState.password.trim() || authLoading}
                style={{ width: '100%', padding: '14px', background: (authState.email.trim() && authState.password.trim()) ? 'linear-gradient(135deg, #F58220 0%, #D96E14 100%)' : '#E0E0E0', color: 'white', border: 'none', borderRadius: '10px', fontSize: '15px', fontWeight: 700, cursor: (authState.email.trim() && authState.password.trim()) ? 'pointer' : 'not-allowed' }}
              >
                {authLoading ? '🔄 Signing in...' : 'Sign In →'}
              </button>
            </div>
          )}

          {authMode === 'signup' && (
            <div>
              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#F58220', marginBottom: '0.5rem', textTransform: 'uppercase' }}>Full Name</label>
                <input
                  type="text"
                  value={authState.name}
                  onChange={(e) => setAuthState({ ...authState, name: e.target.value })}
                  placeholder="Jane Doe"
                  autoFocus
                  style={{ width: '100%', padding: '12px', border: '2px solid #E0E0E0', borderRadius: '8px', fontSize: '13px', boxSizing: 'border-box', outline: 'none' }}
                />
              </div>
              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#F58220', marginBottom: '0.5rem', textTransform: 'uppercase' }}>Email</label>
                <input
                  type="email"
                  value={authState.email}
                  onChange={(e) => setAuthState({ ...authState, email: e.target.value })}
                  placeholder="you@example.com"
                  style={{ width: '100%', padding: '12px', border: '2px solid #E0E0E0', borderRadius: '8px', fontSize: '13px', boxSizing: 'border-box', outline: 'none' }}
                />
              </div>
              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#F58220', marginBottom: '0.5rem', textTransform: 'uppercase' }}>Password</label>
                <input
                  type="password"
                  value={authState.password}
                  onChange={(e) => setAuthState({ ...authState, password: e.target.value })}
                  placeholder="••••••••"
                  style={{ width: '100%', padding: '12px', border: '2px solid #E0E0E0', borderRadius: '8px', fontSize: '13px', boxSizing: 'border-box', outline: 'none' }}
                />
              </div>
              <button
                onClick={handleSignupSubmit}
                disabled={!authState.email.trim() || !authState.password.trim() || !authState.name.trim() || authLoading}
                style={{ width: '100%', padding: '12px', background: (authState.email.trim() && authState.password.trim() && authState.name.trim()) ? 'linear-gradient(135deg, #F58220 0%, #D96E14 100%)' : '#E0E0E0', color: 'white', border: 'none', borderRadius: '8px', fontSize: '14px', fontWeight: 700, cursor: (authState.email.trim() && authState.password.trim() && authState.name.trim()) ? 'pointer' : 'not-allowed' }}
              >
                {authLoading ? '🔄 Creating...' : 'Create Account →'}
              </button>
            </div>
          )}
        </div>
      </div>
    )
  }

  // WELCOME BACK STAGE
  if (stage === 'welcome-back' && returningCandidate) {
    const handleContinueApplication = () => {
      localStorage.setItem('candidateData', JSON.stringify({
        email: returningCandidate.email,
        name: returningCandidate.name,
        role: returningCandidate.role,
        isGuest: false,
        isReturning: true
      }))
      setCandidateName(returningCandidate.name)
      setStage('relationship')
    }

    return (
      <div style={{ display: 'flex', height: '100vh', background: '#F5F5F5', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '2rem' }}>
        <Header />
        <div style={{ maxWidth: '600px', width: '100%', background: 'white', borderRadius: '16px', padding: '3rem', boxShadow: '0 10px 40px rgba(0,0,0,0.1)' }}>
          <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
            <div style={{ fontSize: '56px', marginBottom: '1rem' }}>👋</div>
            <h1 style={{ fontSize: '32px', fontWeight: 700, margin: '0 0 0.5rem 0', color: '#0B1F3A' }}>
              Welcome back!
            </h1>
            <p style={{ fontSize: '16px', color: '#666666', margin: 0 }}>{returningCandidate.name || returningCandidate.email.split('@')[0]}</p>
          </div>

          <div style={{ background: 'linear-gradient(135deg, #FEF3E6 0%, #FFF8F0 100%)', border: '2px solid #F58220', borderRadius: '12px', padding: '1.5rem', marginBottom: '2rem' }}>
            <div style={{ display: 'flex', gap: '1rem', alignItems: 'flex-start' }}>
              <div style={{ fontSize: '28px' }}>📄</div>
              <div>
                <h3 style={{ fontSize: '14px', fontWeight: 700, margin: '0 0 0.5rem 0', color: '#0B1F3A' }}>We have your info!</h3>
                <p style={{ fontSize: '13px', color: '#666666', margin: '0 0 0.5rem 0' }}>
                  <strong>Last resume:</strong> {returningCandidate.resumeDate || 'Recently'}
                </p>
                <p style={{ fontSize: '13px', color: '#666666', margin: 0 }}>
                  <strong>Skills:</strong> {returningCandidate.skillsTags?.join(', ') || 'On file'}
                </p>
              </div>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <button
              onClick={handleContinueApplication}
              style={{ padding: '14px 24px', background: 'linear-gradient(135deg, #F58220 0%, #D96E14 100%)', color: 'white', border: 'none', borderRadius: '10px', fontSize: '15px', fontWeight: 700, cursor: 'pointer', boxShadow: '0 4px 15px rgba(245, 130, 32, 0.3)' }}
            >
              ⚡ Continue
            </button>
            <button
              onClick={() => setStage('resume')}
              style={{ padding: '14px 24px', background: 'white', color: '#F58220', border: '2px solid #F58220', borderRadius: '10px', fontSize: '15px', fontWeight: 700, cursor: 'pointer' }}
            >
              📄 New Resume
            </button>
          </div>
        </div>
      </div>
    )
  }

  // DYNAMIC CHAT STAGE (Relationship Building + Analysis + Clarifications)
  if (stage === 'relationship' || stage === 'analysis') {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: 'linear-gradient(to bottom, #0B1F3A 0%, #1a2d3f 50%, #F5F5F5 100%)' }}>
        <Header />

        <div style={{ display: 'flex', height: 'calc(100vh - 57px)', gap: '0', position: 'relative' }}>
          {/* Chat Area - Full Screen */}
          <div style={{ flex: 1, background: 'white', display: 'flex', flexDirection: 'column', position: 'relative', overflow: 'hidden' }}>
            {/* Job Context Button */}
            <button
              onClick={() => setShowJobContext(!showJobContext)}
              style={{
                position: 'absolute',
                top: '16px',
                right: '16px',
                padding: '10px 16px',
                background: showJobContext ? '#D96E14' : '#F58220',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                fontSize: '12px',
                fontWeight: 700,
                cursor: 'pointer',
                zIndex: 10,
                boxShadow: '0 4px 12px rgba(245, 130, 32, 0.3)',
                transition: 'all 0.3s'
              }}
              onMouseEnter={(e) => e.currentTarget.style.transform = 'translateY(-2px)'}
              onMouseLeave={(e) => e.currentTarget.style.transform = 'translateY(0)'}
            >
              {showJobContext ? '✕ Hide' : '📋 Job Context'}
            </button>

            {/* Messages Area */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px', paddingTop: '60px' }}>
              {messages.map((msg, idx) => (
                <div key={idx} style={{ display: 'flex', justifyContent: msg.type === 'bot' ? 'flex-start' : 'flex-end' }}>
                  <div style={{
                    maxWidth: '70%',
                    padding: msg.type === 'bot' ? '14px 18px' : '14px 18px',
                    borderRadius: '16px',
                    background: msg.type === 'bot' ? 'linear-gradient(135deg, #F0F0F0 0%, #FFFFFF 100%)' : 'linear-gradient(135deg, #F58220 0%, #D96E14 100%)',
                    color: msg.type === 'bot' ? '#333' : 'white',
                    fontSize: '14px',
                    lineHeight: '1.6',
                    fontWeight: msg.type === 'bot' ? 500 : 500,
                    boxShadow: msg.type === 'bot' ? '0 2px 8px rgba(0,0,0,0.05)' : '0 2px 8px rgba(245, 130, 32, 0.2)'
                  }}>
                    {msg.text}
                  </div>
                </div>
              ))}
              {thinking && (
                <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
                  <div style={{ padding: '14px 18px', borderRadius: '16px', background: '#F0F0F0', color: '#666', fontSize: '14px' }}>
                    ⚡ Thunder is thinking...
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input Area - Ask Thunder */}
            <div style={{ borderTop: '2px solid #E0E0E0', padding: '20px 24px', background: 'white', display: 'flex', gap: '12px', alignItems: 'flex-end' }}>
              <div style={{ flex: 1, position: 'relative' }}>
                <input
                  type="text"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="Ask Thunder anything..."
                  disabled={thinking}
                  autoFocus
                  style={{ width: '100%', padding: '14px 16px', border: '2px solid #E0E0E0', borderRadius: '10px', fontSize: '14px', outline: 'none', transition: 'all 0.3s', opacity: thinking ? 0.6 : 1, cursor: thinking ? 'not-allowed' : 'text', fontWeight: 500 }}
                  onFocus={(e) => { if (!thinking) e.currentTarget.style.borderColor = '#F58220' }}
                  onBlur={(e) => { e.currentTarget.style.borderColor = '#E0E0E0' }}
                />
              </div>
              <button
                onClick={handleAskThunder}
                disabled={!inputValue.trim() || thinking}
                style={{ padding: '14px 28px', background: (inputValue.trim() && !thinking) ? 'linear-gradient(135deg, #F58220 0%, #D96E14 100%)' : '#E0E0E0', color: 'white', border: 'none', borderRadius: '10px', fontSize: '14px', fontWeight: 700, cursor: (inputValue.trim() && !thinking) ? 'pointer' : 'not-allowed', whiteSpace: 'nowrap', boxShadow: (inputValue.trim() && !thinking) ? '0 4px 12px rgba(245, 130, 32, 0.3)' : 'none', transition: 'all 0.3s', display: 'flex', alignItems: 'center', gap: '6px' }}
                onMouseEnter={(e) => { if (inputValue.trim() && !thinking) e.currentTarget.style.transform = 'translateY(-2px)' }}
                onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)' }}
              >
                {thinking ? '🔄' : '⚡ Ask'}
              </button>
            </div>
          </div>

          {/* Slide-out Job Context Panel */}
          {showJobContext && (
            <div style={{
              position: 'absolute',
              right: 0,
              top: 57,
              height: 'calc(100vh - 57px)',
              width: '380px',
              background: 'linear-gradient(135deg, #0B1F3A 0%, #1a2d3f 100%)',
              borderLeft: '2px solid #F58220',
              padding: '24px',
              overflowY: 'auto',
              zIndex: 5,
              boxShadow: '-4px 0 20px rgba(0,0,0,0.2)',
              animation: 'slideIn 0.3s ease-out'
            }}>
              <style>{`
                @keyframes slideIn {
                  from { transform: translateX(100%); opacity: 0; }
                  to { transform: translateX(0); opacity: 1; }
                }
              `}</style>
              <div style={{ marginBottom: '1.5rem' }}>
                <h2 style={{ fontSize: '22px', fontWeight: 700, margin: '0 0 0.5rem 0', color: '#F58220' }}>{jobDetails.title}</h2>
                <p style={{ fontSize: '13px', color: '#FFF', opacity: 0.8, marginBottom: 0, fontWeight: 500 }}>{jobDetails.company}</p>
              </div>

              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '1.5rem' }}>
                {[jobDetails.type, jobDetails.location, jobDetails.experience].map(tag => (
                  <span key={tag} style={{ display: 'inline-block', background: 'linear-gradient(135deg, #F58220 0%, #D96E14 100%)', color: 'white', padding: '6px 12px', borderRadius: '6px', fontSize: '12px', fontWeight: 700 }}>{tag}</span>
                ))}
              </div>

              <h3 style={{ fontSize: '13px', fontWeight: 700, color: '#F58220', marginBottom: '1rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Required Skills</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {jobDetails.skills.map(skill => (
                  <div key={skill} style={{ fontSize: '13px', color: '#FFF', padding: '10px', background: 'rgba(245, 130, 32, 0.1)', borderLeft: '2px solid #F58220', borderRadius: '6px', fontWeight: 500 }}>✓ {skill}</div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    )
  }

  // RESUME STAGE
  if (stage === 'resume') {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: 'linear-gradient(135deg, #0B1F3A 0%, #1a2d3f 50%, #F5F5F5 100%)' }}>
        <Header />
        <div style={{ flex: 1, padding: '2rem', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ maxWidth: '600px', background: 'white', borderRadius: '16px', padding: '2.5rem', boxShadow: '0 10px 40px rgba(0,0,0,0.15)' }}>
            <div style={{ fontSize: '56px', marginBottom: '1rem', textAlign: 'center' }}>📄</div>
            <h2 style={{ fontSize: '24px', fontWeight: 700, margin: '0 0 0.5rem 0', color: '#0B1F3A', textAlign: 'center' }}>Upload Your Resume</h2>
            <p style={{ fontSize: '14px', color: '#666', marginBottom: '1.5rem', textAlign: 'center', fontWeight: 500 }}>Let ⚡ Thunder analyze your fit</p>

            {!resumeFile ? (
              <label style={{ display: 'block' }}>
                <input
                  type="file"
                  onChange={handleResumeSelect}
                  accept=".pdf,.doc,.docx,.txt"
                  style={{ display: 'none' }}
                />
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', cursor: 'pointer', padding: '2rem', background: '#F5F5F5', borderRadius: '12px', border: '2px dashed #F58220', transition: 'all 0.3s' }}
                  onMouseEnter={(e) => e.currentTarget.style.background = '#FEF3E6'}
                  onMouseLeave={(e) => e.currentTarget.style.background = '#F5F5F5'}
                >
                  <div style={{ fontSize: '32px', marginBottom: '0.75rem' }}>📤</div>
                  <span style={{ display: 'inline-block', padding: '12px 28px', background: 'linear-gradient(135deg, #F58220 0%, #D96E14 100%)', color: 'white', borderRadius: '10px', fontSize: '14px', fontWeight: 700, cursor: 'pointer' }}>
                    Choose File
                  </span>
                  <p style={{ fontSize: '12px', color: '#999', marginTop: '1rem', marginBottom: 0 }}>PDF, DOC, DOCX, or TXT</p>
                </div>
              </label>
            ) : (
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '40px', marginBottom: '1rem' }}>✅</div>
                <h3 style={{ fontSize: '16px', fontWeight: 700, margin: '0 0 0.5rem 0', color: '#2E7D32' }}>{resumeFile.name}</h3>
                <p style={{ fontSize: '12px', color: '#666', marginBottom: '1.5rem' }}>{(resumeFile.size / 1024).toFixed(1)} KB</p>

                <button
                  onClick={handleResumeUpload}
                  disabled={uploading}
                  style={{ padding: '14px 32px', background: 'linear-gradient(135deg, #F58220 0%, #D96E14 100%)', color: 'white', border: 'none', borderRadius: '10px', fontSize: '14px', fontWeight: 700, cursor: uploading ? 'not-allowed' : 'pointer', opacity: uploading ? 0.6 : 1, boxShadow: '0 4px 15px rgba(245, 130, 32, 0.3)', transition: 'all 0.3s', marginBottom: '1rem' }}
                >
                  {uploading ? '🔄 Analyzing...' : '⚡ Let Thunder Analyze'}
                </button>

                <button
                  onClick={() => { setResumeFile(null); setResumeText('') }}
                  style={{ display: 'block', margin: '0 auto', padding: '8px 16px', background: 'transparent', color: '#F58220', border: '1px solid #F58220', borderRadius: '8px', fontSize: '13px', fontWeight: 600, cursor: 'pointer' }}
                >
                  Choose Different File
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    )
  }

  // COMPLETION STAGE
  if (stage === 'complete') {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: 'linear-gradient(135deg, #0B1F3A 0%, #1a2d3f 50%, #F5F5F5 100%)' }}>
        <Header />
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '2rem' }}>
          <div style={{ maxWidth: '600px', background: 'white', borderRadius: '16px', padding: '3rem', textAlign: 'center', boxShadow: '0 10px 40px rgba(0,0,0,0.15)' }}>
            <div style={{ fontSize: '72px', marginBottom: '1rem', animation: 'float 2s ease-in-out infinite' }}>🎉</div>
            <h1 style={{ fontSize: '32px', fontWeight: 700, margin: '0 0 0.5rem 0', color: '#0B1F3A' }}>You're All Set!</h1>
            <p style={{ fontSize: '16px', color: '#666', margin: '0 0 2rem 0', lineHeight: '1.6', fontWeight: 500 }}>
              ⚡ Thunder has reviewed your application. We'll be in touch within 3 business days with next steps.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <button
                onClick={() => router.push('/dashboard')}
                style={{ padding: '14px 32px', background: 'linear-gradient(135deg, #F58220 0%, #D96E14 100%)', color: 'white', border: 'none', borderRadius: '10px', fontSize: '14px', fontWeight: 700, cursor: 'pointer', boxShadow: '0 4px 15px rgba(245, 130, 32, 0.3)', transition: 'all 0.3s' }}
                onMouseEnter={(e) => e.currentTarget.style.transform = 'translateY(-2px)'}
                onMouseLeave={(e) => e.currentTarget.style.transform = 'translateY(0)'}
              >
                📊 View Application Status
              </button>
              <button
                onClick={() => router.push('/jobs')}
                style={{ padding: '14px 32px', background: 'transparent', color: '#0B1F3A', border: '2px solid #0B1F3A', borderRadius: '10px', fontSize: '14px', fontWeight: 700, cursor: 'pointer' }}
              >
                ← Back to Jobs
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return null
}
