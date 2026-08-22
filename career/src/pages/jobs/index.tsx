import { useState, useEffect } from 'react'
import Link from 'next/link'
import axios from 'axios'

interface Job {
  id: string
  title: string
  description: string
  location?: string
  experience_years_required?: number
  skills_required?: any
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [location, setLocation] = useState('all')
  const [department, setDepartment] = useState('all')
  const [candidateName, setCandidateName] = useState('')

  useEffect(() => {
    // Load candidate data from localStorage
    const stored = localStorage.getItem('candidateData')
    if (stored) {
      const data = JSON.parse(stored)
      setCandidateName(data.name || data.email)
    }
  }, [])

  useEffect(() => {
    const loadJobs = async () => {
      try {
        const response = await axios.get('http://localhost:8080/api/v1/careers/jobs')
        setJobs(response.data || [])
      } catch (err) {
        console.error('Failed to load jobs:', err)
        // Fallback to demo jobs if API unavailable
        setJobs([
          {
            id: 'job_001',
            title: 'Business Delivery Consultant',
            description: 'Lead customer implementations and drive business outcomes.',
            location: 'San Francisco, CA',
            experience_years_required: 5
          },
          {
            id: 'job_002',
            title: 'Senior Software Engineer',
            description: 'Build and scale our platform. Mentor junior engineers.',
            location: 'Remote',
            experience_years_required: 7
          },
          {
            id: 'job_003',
            title: 'Product Manager',
            description: 'Define product strategy and roadmap.',
            location: 'San Francisco, CA',
            experience_years_required: 4
          }
        ])
      } finally {
        setLoading(false)
      }
    }

    loadJobs()
  }, [])

  return (
    <div style={{ background: 'var(--surface-0)', minHeight: '100vh' }}>
      <nav style={{ background: 'white', borderBottom: '0.5px solid var(--border)', padding: '1rem 2rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1 style={{ fontSize: '20px', fontWeight: 500, color: '#185FA5' }}>🚀 BlitzenX Careers</h1>
        <div style={{ display: 'flex', gap: '2rem', alignItems: 'center' }}>
          <a href="#about" style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>About</a>
          <a href="#culture" style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>Culture</a>
          {candidateName ? (
            <Link href="/dashboard" style={{ color: '#185FA5', fontSize: '14px', fontWeight: 500, textDecoration: 'none' }}>
              👤 {candidateName.split(' ')[0]}
            </Link>
          ) : (
            <Link href="/apply" style={{ color: '#185FA5', fontSize: '14px', fontWeight: 500, textDecoration: 'none' }}>
              Login / Sign Up
            </Link>
          )}
        </div>
      </nav>

      <div style={{ background: 'linear-gradient(135deg, #185FA5 0%, #0C447C 100%)', color: 'white', padding: '3rem 2rem', textAlign: 'center' }}>
        <h2 style={{ fontSize: '32px', fontWeight: 500, marginBottom: '0.5rem' }}>Join our team</h2>
        <p style={{ fontSize: '16px', opacity: 0.9, marginBottom: '1.5rem' }}>Build the future of hiring with us</p>
      </div>

      <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '2rem', display: 'grid', gridTemplateColumns: '200px 1fr', gap: '2rem' }}>
        <div style={{ background: 'white', borderRadius: '12px', border: '0.5px solid var(--border)', padding: '1.5rem', height: 'fit-content' }}>
          <h3 style={{ fontSize: '14px', fontWeight: 500, marginBottom: '1rem' }}>Filter</h3>

          <div style={{ marginBottom: '1.5rem' }}>
            <label style={{ display: 'block', fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '8px' }}>Location</label>
            <select value={location} onChange={(e) => setLocation(e.target.value)} style={{ width: '100%', padding: '8px', border: '0.5px solid var(--border)', borderRadius: 'var(--radius)', fontSize: '13px' }}>
              <option value="all">All locations</option>
              <option value="sf">San Francisco, CA</option>
              <option value="remote">Remote</option>
              <option value="ny">New York, NY</option>
            </select>
          </div>

          <div style={{ marginBottom: '1.5rem' }}>
            <label style={{ display: 'block', fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '8px' }}>Department</label>
            <select value={department} onChange={(e) => setDepartment(e.target.value)} style={{ width: '100%', padding: '8px', border: '0.5px solid var(--border)', borderRadius: 'var(--radius)', fontSize: '13px' }}>
              <option value="all">All departments</option>
              <option value="eng">Engineering</option>
              <option value="product">Product</option>
              <option value="sales">Sales</option>
            </select>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '1.5rem' }}>
          {loading ? (
            <div style={{ gridColumn: '1 / -1', textAlign: 'center', padding: '2rem' }}>
              <p style={{ color: 'var(--text-secondary)' }}>Loading jobs...</p>
            </div>
          ) : error ? (
            <div style={{ gridColumn: '1 / -1', textAlign: 'center', padding: '2rem' }}>
              <p style={{ color: '#D32F2F' }}>{error}</p>
            </div>
          ) : jobs.length === 0 ? (
            <div style={{ gridColumn: '1 / -1', textAlign: 'center', padding: '2rem' }}>
              <p style={{ color: 'var(--text-secondary)' }}>No open positions at this time.</p>
            </div>
          ) : (
            jobs.map((job) => (
              <div key={job.id} style={{ background: 'white', borderRadius: '12px', border: '0.5px solid var(--border)', padding: '1.5rem', transition: 'all 0.2s', cursor: 'pointer' }} onMouseEnter={(e) => { e.currentTarget.style.borderColor = '#185FA5'; e.currentTarget.style.boxShadow = '0 2px 8px rgba(24,95,165,0.1)' }} onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.boxShadow = 'none' }}>
                <div style={{ marginBottom: '1rem' }}>
                  <h3 style={{ fontSize: '16px', fontWeight: 500, margin: 0 }}>{job.title}</h3>
                  <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: '4px 0 0 0' }}>BlitzenX</p>
                </div>

                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '1rem' }}>
                  <span style={{ display: 'inline-block', background: '#E6F1FB', color: '#185FA5', padding: '4px 12px', borderRadius: 'var(--radius)', fontSize: '12px', fontWeight: 500 }}>Full-time</span>
                  {job.location && <span style={{ display: 'inline-block', background: '#E6F1FB', color: '#185FA5', padding: '4px 12px', borderRadius: 'var(--radius)', fontSize: '12px', fontWeight: 500 }}>{job.location}</span>}
                  {job.experience_years_required && <span style={{ display: 'inline-block', background: '#E6F1FB', color: '#185FA5', padding: '4px 12px', borderRadius: 'var(--radius)', fontSize: '12px', fontWeight: 500 }}>{job.experience_years_required}+ years</span>}
                </div>

                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: '1.5', marginBottom: '1rem' }}>{job.description}</p>

                <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <Link href={`/apply?jobId=${job.id}`} style={{ padding: '10px 16px', background: '#185FA5', color: 'white', borderRadius: 'var(--radius)', fontSize: '14px', fontWeight: 500 }}>
                    Apply now →
                  </Link>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
