import { useState, useEffect } from 'react'
import Link from 'next/link'
import axios from 'axios'

interface Application {
  id: string
  job_id: string
  job_title: string
  applied_date: string
  status: 'applied' | 'screening' | 'interview' | 'offer' | 'rejected'
  fit_score: number
  last_update?: string
  job_location?: string
  next_step?: string
  recruiter_name?: string
  interview_date?: string
}

interface MatchingJob {
  id: string
  title: string
  location?: string
  match_score: number
  is_applied: boolean
}

const TIMELINE_STAGES = [
  { key: 'applied', label: 'Applied', icon: '📝' },
  { key: 'screening', label: 'Recruiter Review', icon: '👥' },
  { key: 'interview', label: 'Interview', icon: '🎯' },
  { key: 'offer', label: 'Offer', icon: '🎉' },
]

export default function CandidateDashboard() {
  const [candidateName, setCandidateName] = useState('')
  const [candidateEmail, setCandidateEmail] = useState('')
  const [candidateRole, setCandidateRole] = useState('Job Applicant')
  const [activeTab, setActiveTab] = useState<'applications' | 'matches' | 'settings'>('applications')

  const [applications, setApplications] = useState<Application[]>([])

  const [matchingJobs, setMatchingJobs] = useState<MatchingJob[]>([
    {
      id: 'job_003',
      title: 'Product Manager',
      location: 'San Francisco, CA',
      match_score: 72,
      is_applied: false
    },
    {
      id: 'job_004',
      title: 'Solutions Architect',
      location: 'Remote',
      match_score: 81,
      is_applied: false
    }
  ])

  const statusColors: Record<string, { bg: string; text: string; label: string; timeline: string }> = {
    applied: { bg: '#FFF8F0', text: '#F58220', label: 'Applied', timeline: '#F58220' },
    screening: { bg: '#F0F4FB', text: '#0B1F3A', label: 'Under Review', timeline: '#0B1F3A' },
    interview: { bg: '#FEF5E0', text: '#FFB84D', label: 'Interview Scheduled', timeline: '#FFB84D' },
    offer: { bg: '#E8F5E9', text: '#2ECC71', label: 'Offer Extended', timeline: '#2ECC71' },
    rejected: { bg: '#FFEBEE', text: '#E74C3C', label: 'Not Selected', timeline: '#E74C3C' }
  }

  useEffect(() => {
    // Load candidate data from localStorage
    const stored = localStorage.getItem('candidateData')
    if (stored) {
      const data = JSON.parse(stored)
      setCandidateName(data.name || data.email || 'Candidate')
      setCandidateEmail(data.email || '')
      if (data.role) setCandidateRole(data.role)
    } else {
      // Not logged in, redirect to jobs
      window.location.href = '/jobs'
    }
  }, [])

  useEffect(() => {
    // Load applications from API
    const loadApplications = async () => {
      if (!candidateEmail) return
      try {
        const response = await axios.get(`http://localhost:8080/api/v1/careers/applications/by-email/${candidateEmail}`)
        if (response.data.applications && response.data.applications.length > 0) {
          // Map API response to Application interface
          const mappedApps = response.data.applications.map((app: any) => ({
            id: app.id,
            job_id: app.job_id,
            job_title: app.job_title,
            applied_date: app.applied_date,
            status: app.status as any,
            fit_score: Math.round(app.fit_score || 0),
            last_update: app.last_update
          }))
          setApplications(mappedApps)
        }
      } catch (err) {
        console.error('Failed to load applications:', err)
        // Fallback to empty state - let user see dashboard anyway
      }
    }
    loadApplications()
  }, [candidateEmail])

  const handleLogout = () => {
    localStorage.removeItem('candidateData')
    window.location.href = '/jobs'
  }

  return (
    <div style={{ background: 'var(--surface-0)', minHeight: '100vh' }}>
      {/* Header */}
      <nav style={{ background: '#0B1F3A', borderBottom: '3px solid #F58220', padding: '1rem 2rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Link href="/jobs" style={{ fontSize: '20px', fontWeight: 700, color: '#F58220', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '8px' }}>
          ⚡ BlitzenX Careers
        </Link>
        <div style={{ display: 'flex', gap: '2rem', alignItems: 'center' }}>
          <span style={{ fontSize: '14px', color: '#FFF' }}>{candidateName || candidateEmail}</span>
          <button
            onClick={handleLogout}
            style={{
              padding: '8px 16px',
              background: 'transparent',
              color: '#F58220',
              border: '1px solid #F58220',
              borderRadius: '6px',
              fontSize: '13px',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'all 0.2s'
            }}
          >
            Sign Out
          </button>
        </div>
      </nav>

      <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '2rem' }}>
        {/* Profile Card */}
        <div style={{ background: 'linear-gradient(135deg, #0B1F3A 0%, #0B3A5A 100%)', borderRadius: '12px', padding: '2rem', marginBottom: '2rem', boxShadow: '0 4px 12px rgba(0,0,0,0.1)', color: 'white' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
            <div>
              <h1 style={{ fontSize: '24px', fontWeight: 700, margin: '0 0 0.5rem 0', color: '#FFF' }}>
                Welcome, {candidateName || 'Candidate'}! 👋
              </h1>
              <p style={{ fontSize: '14px', color: '#B8D4E8', margin: 0 }}>
                {candidateRole} • {candidateEmail}
              </p>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '36px', fontWeight: 700, color: '#F58220' }}>
                {applications.length}
              </div>
              <div style={{ fontSize: '13px', color: '#B8D4E8' }}>Applications</div>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '2rem', borderBottom: '2px solid #F58220' }}>
          {(['applications', 'matches', 'settings'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              style={{
                padding: '12px 20px',
                background: activeTab === tab ? '#F58220' : 'transparent',
                color: activeTab === tab ? 'white' : '#0B1F3A',
                border: 'none',
                borderRadius: '6px 6px 0 0',
                fontSize: '14px',
                fontWeight: 600,
                cursor: 'pointer',
                textTransform: 'capitalize',
                transition: 'all 0.2s'
              }}
            >
              {tab === 'applications' ? '📋 My Applications' : tab === 'matches' ? '⭐ Matching Jobs' : '⚙️ Settings'}
            </button>
          ))}
        </div>

        {/* Applications Tab */}
        {activeTab === 'applications' && (
          <div>
            <h2 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '1.5rem', color: '#2c2c2a' }}>
              Your Applications
            </h2>
            {applications.length === 0 ? (
              <div style={{ background: 'white', padding: '2rem', borderRadius: 'var(--radius)', textAlign: 'center', border: '0.5px solid var(--border)' }}>
                <div style={{ fontSize: '48px', marginBottom: '1rem' }}>📋</div>
                <p style={{ color: 'var(--text-secondary)', marginBottom: '1rem' }}>No applications yet</p>
                <Link href="/jobs"
                  style={{
                    display: 'inline-block',
                    padding: '10px 20px',
                    background: '#F58220',
                    color: 'white',
                    borderRadius: 'var(--radius)',
                    textDecoration: 'none',
                    fontWeight: 600,
                    fontSize: '14px'
                  }}
                >
                  Browse Jobs
                </Link>
              </div>
            ) : (
              <div style={{ display: 'grid', gap: '1.5rem' }}>
                {applications.map((app) => {
                  const status = statusColors[app.status]
                  const stageIndex = TIMELINE_STAGES.findIndex(s => s.key === app.status)
                  const fitColor = app.fit_score >= 70 ? '#2ECC71' : app.fit_score >= 50 ? '#F58220' : '#E74C3C'

                  return (
                    <div key={app.id} style={{ background: 'white', padding: '1.5rem', borderRadius: '12px', border: '0.5px solid var(--border)', boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}>
                      {/* Header */}
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '1rem', marginBottom: '1.5rem' }}>
                        <div>
                          <h3 style={{ fontSize: '16px', fontWeight: 700, margin: '0 0 0.5rem 0', color: '#0B1F3A' }}>
                            {app.job_title}
                          </h3>
                          {app.job_location && (
                            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: 0 }}>
                              📍 {app.job_location}
                            </p>
                          )}
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '0.5rem' }}>
                          <div style={{
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            backgroundColor: fitColor + '15',
                            border: `2px solid ${fitColor}`,
                            borderRadius: '8px',
                            padding: '6px 10px',
                            minWidth: '55px'
                          }}>
                            <div style={{ fontSize: '16px', fontWeight: 700, color: '#0B1F3A' }}>
                              {app.fit_score}%
                            </div>
                            <div style={{ fontSize: '10px', color: '#666', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.3px' }}>
                              Fit
                            </div>
                          </div>
                          <div style={{
                            display: 'inline-block',
                            padding: '4px 10px',
                            background: status.bg,
                            color: status.text,
                            borderRadius: '6px',
                            fontSize: '12px',
                            fontWeight: 600
                          }}>
                            {status.label}
                          </div>
                        </div>
                      </div>

                      {/* Timeline */}
                      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0', marginBottom: '1.5rem', justifyContent: 'space-between' }}>
                        {TIMELINE_STAGES.map((stage, index) => (
                          <div key={stage.key} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', position: 'relative' }}>
                            <div
                              style={{
                                width: '36px',
                                height: '36px',
                                borderRadius: '50%',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                fontSize: '16px',
                                backgroundColor: index <= stageIndex ? status.timeline + '20' : '#F0F0F0',
                                border: `2px solid ${index <= stageIndex ? status.timeline : '#DDD'}`,
                                marginBottom: '8px',
                              }}
                            >
                              {stage.icon}
                            </div>
                            <div style={{ fontSize: '11px', fontWeight: 600, color: '#0B1F3A', textAlign: 'center', lineHeight: '1.2' }}>
                              {stage.label.split(' ')[0]}
                              {stage.label.includes(' ') && <div>{stage.label.split(' ').slice(1).join(' ')}</div>}
                            </div>
                            {index === stageIndex && app.status !== 'rejected' && (
                              <div style={{ fontSize: '9px', color: '#F58220', fontWeight: 700, marginTop: '2px', textTransform: 'uppercase' }}>
                                Now
                              </div>
                            )}
                            {index < TIMELINE_STAGES.length - 1 && (
                              <div
                                style={{
                                  position: 'absolute',
                                  top: '18px',
                                  left: '50%',
                                  width: '100%',
                                  height: '2px',
                                  backgroundColor: index < stageIndex ? status.timeline : '#DDD',
                                  zIndex: -1,
                                }}
                              />
                            )}
                          </div>
                        ))}
                      </div>

                      {/* Next Steps & Details */}
                      <div style={{ borderTop: '1px solid #E8E8E8', paddingTop: '1rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '1rem' }}>
                        {app.next_step && (
                          <div>
                            <div style={{ fontSize: '10px', color: '#999', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.3px', marginBottom: '4px' }}>
                              Next Step
                            </div>
                            <div style={{ fontSize: '13px', color: '#0B1F3A', fontWeight: 500 }}>
                              {app.next_step}
                            </div>
                          </div>
                        )}
                        {app.recruiter_name && (
                          <div>
                            <div style={{ fontSize: '10px', color: '#999', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.3px', marginBottom: '4px' }}>
                              Your Recruiter
                            </div>
                            <div style={{ fontSize: '13px', color: '#0B1F3A', fontWeight: 500 }}>
                              {app.recruiter_name}
                            </div>
                          </div>
                        )}
                        {app.interview_date && (
                          <div>
                            <div style={{ fontSize: '10px', color: '#999', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.3px', marginBottom: '4px' }}>
                              Interview Date
                            </div>
                            <div style={{ fontSize: '13px', color: '#F58220', fontWeight: 600 }}>
                              {new Date(app.interview_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                            </div>
                          </div>
                        )}
                        <div>
                          <div style={{ fontSize: '10px', color: '#999', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.3px', marginBottom: '4px' }}>
                            Applied
                          </div>
                          <div style={{ fontSize: '13px', color: '#0B1F3A', fontWeight: 500 }}>
                            {new Date(app.applied_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                          </div>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )}

        {/* Matches Tab */}
        {activeTab === 'matches' && (
          <div>
            <h2 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '1rem', color: '#2c2c2a' }}>
              Jobs Matching Your Profile
            </h2>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '1.5rem' }}>
              {matchingJobs.map((job) => (
                <div key={job.id} style={{ background: 'white', padding: '1.5rem', borderRadius: 'var(--radius)', border: '0.5px solid var(--border)' }}>
                  <div style={{ marginBottom: '1rem' }}>
                    <h3 style={{ fontSize: '16px', fontWeight: 600, margin: '0 0 0.5rem 0', color: '#2c2c2a' }}>
                      {job.title}
                    </h3>
                    {job.location && (
                      <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: 0 }}>
                        📍 {job.location}
                      </p>
                    )}
                  </div>

                  <div style={{ marginBottom: '1.5rem', padding: '0.75rem', background: '#F0F7FF', borderRadius: 'var(--radius)' }}>
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>
                      Match Score
                    </div>
                    <div style={{ fontSize: '18px', fontWeight: 600, color: '#185FA5' }}>
                      {job.match_score}%
                    </div>
                  </div>

                  <Link href={`/jobs/${job.id}`}
                    style={{
                      display: 'block',
                      padding: '10px 16px',
                      background: '#185FA5',
                      color: 'white',
                      borderRadius: 'var(--radius)',
                      textDecoration: 'none',
                      textAlign: 'center',
                      fontWeight: 600,
                      fontSize: '14px'
                    }}
                  >
                    {job.is_applied ? '✓ Already Applied' : 'View & Apply'}
                  </Link>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Settings Tab */}
        {activeTab === 'settings' && (
          <div style={{ background: 'white', padding: '2rem', borderRadius: 'var(--radius)', border: '0.5px solid var(--border)' }}>
            <h2 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '1.5rem', color: '#2c2c2a' }}>
              Account Settings
            </h2>

            <div style={{ marginBottom: '2rem' }}>
              <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                Email Address
              </label>
              <input
                type="email"
                value={candidateEmail}
                disabled
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  border: '0.5px solid var(--border)',
                  borderRadius: 'var(--radius)',
                  fontSize: '14px',
                  background: '#F5F5F5',
                  color: 'var(--text-primary)',
                  boxSizing: 'border-box'
                }}
              />
            </div>

            <div style={{ marginBottom: '2rem' }}>
              <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                Full Name
              </label>
              <input
                type="text"
                value={candidateName}
                disabled
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  border: '0.5px solid var(--border)',
                  borderRadius: 'var(--radius)',
                  fontSize: '14px',
                  background: '#F5F5F5',
                  color: 'var(--text-primary)',
                  boxSizing: 'border-box'
                }}
              />
            </div>

            <div style={{ marginBottom: '2rem' }}>
              <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                Role
              </label>
              <div style={{
                padding: '10px 12px',
                border: '0.5px solid var(--border)',
                borderRadius: 'var(--radius)',
                fontSize: '14px',
                background: '#F5F5F5',
                color: 'var(--text-primary)'
              }}>
                {candidateRole}
              </div>
            </div>

            <button
              onClick={handleLogout}
              style={{
                padding: '12px 24px',
                background: '#D32F2F',
                color: 'white',
                border: 'none',
                borderRadius: 'var(--radius)',
                fontWeight: 600,
                fontSize: '14px',
                cursor: 'pointer'
              }}
            >
              Sign Out
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
