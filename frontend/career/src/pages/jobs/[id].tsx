import { useState, useEffect } from 'react'
import { useRouter } from 'next/router'
import Link from 'next/link'
import axios from 'axios'

interface JobDetail {
  id: string
  title: string
  description: string
  location?: string
  experience_years_required?: number
  skills_required?: any[]
  salary_range_min_usd_cents?: number
  salary_range_max_usd_cents?: number
}

export default function JobDetailsPage() {
  const router = useRouter()
  const { id } = router.query
  const [job, setJob] = useState<JobDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!id) return

    const loadJob = async () => {
      try {
        const response = await axios.get(`http://localhost:8080/api/v1/careers/jobs/${id}`)
        setJob(response.data)
      } catch (err) {
        console.error('Failed to load job:', err)
        setError('Job not found')
        // Fallback demo job
        setJob({
          id: id as string,
          title: 'Business Delivery Consultant',
          description: 'Lead customer implementations and drive business outcomes. Work directly with enterprise clients to understand their needs and deliver tailored solutions. Manage project timelines, budgets, and team resources.',
          location: 'San Francisco, CA',
          experience_years_required: 5,
          skills_required: ['Project Management', 'Client Relations', 'Guidewire', 'Business Analysis'],
          salary_range_min_usd_cents: 80000 * 100,
          salary_range_max_usd_cents: 120000 * 100
        })
      } finally {
        setLoading(false)
      }
    }

    loadJob()
  }, [id])

  if (loading) {
    return (
      <div style={{ background: 'var(--surface-0)', minHeight: '100vh', padding: '2rem' }}>
        <p style={{ textAlign: 'center', color: 'var(--text-secondary)' }}>Loading job details...</p>
      </div>
    )
  }

  if (!job || error) {
    return (
      <div style={{ background: 'var(--surface-0)', minHeight: '100vh', padding: '2rem' }}>
        <div style={{ maxWidth: '800px', margin: '0 auto' }}>
          <p style={{ color: '#D32F2F' }}>Job not found</p>
          <Link href="/jobs" style={{ color: '#185FA5', textDecoration: 'underline' }}>
            ← Back to jobs
          </Link>
        </div>
      </div>
    )
  }

  const salaryMin = job.salary_range_min_usd_cents ? (job.salary_range_min_usd_cents / 100).toLocaleString('en-US', { style: 'currency', currency: 'USD' }) : null
  const salaryMax = job.salary_range_max_usd_cents ? (job.salary_range_max_usd_cents / 100).toLocaleString('en-US', { style: 'currency', currency: 'USD' }) : null

  return (
    <div style={{ background: 'var(--surface-0)', minHeight: '100vh' }}>
      {/* Header */}
      <nav style={{ background: 'white', borderBottom: '0.5px solid var(--border)', padding: '1rem 2rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Link href="/jobs" style={{ fontSize: '16px', color: '#185FA5', textDecoration: 'none' }}>
          ← Back to jobs
        </Link>
        <h1 style={{ fontSize: '20px', fontWeight: 500, color: '#185FA5', margin: 0 }}>🚀 BlitzenX Careers</h1>
        <div style={{ width: '100px' }}></div>
      </nav>

      {/* Job Details */}
      <div style={{ maxWidth: '900px', margin: '0 auto', padding: '2rem' }}>
        <div style={{ background: 'white', borderRadius: '12px', border: '0.5px solid var(--border)', padding: '2rem' }}>
          {/* Title & Company */}
          <div style={{ marginBottom: '2rem' }}>
            <h1 style={{ fontSize: '32px', fontWeight: 600, margin: '0 0 0.5rem 0', color: '#2c2c2a' }}>
              {job.title}
            </h1>
            <p style={{ fontSize: '16px', color: 'var(--text-secondary)', margin: '0 0 1rem 0' }}>BlitzenX</p>

            {/* Tags */}
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '1.5rem' }}>
              <span style={{ display: 'inline-block', background: '#E6F1FB', color: '#185FA5', padding: '6px 14px', borderRadius: 'var(--radius)', fontSize: '13px', fontWeight: 500 }}>Full-time</span>
              {job.location && <span style={{ display: 'inline-block', background: '#E6F1FB', color: '#185FA5', padding: '6px 14px', borderRadius: 'var(--radius)', fontSize: '13px', fontWeight: 500 }}>📍 {job.location}</span>}
              {job.experience_years_required && <span style={{ display: 'inline-block', background: '#E6F1FB', color: '#185FA5', padding: '6px 14px', borderRadius: 'var(--radius)', fontSize: '13px', fontWeight: 500 }}>{job.experience_years_required}+ years</span>}
            </div>

            {/* Salary */}
            {(salaryMin || salaryMax) && (
              <div style={{ padding: '1rem', background: '#F5F5F5', borderRadius: 'var(--radius)', marginBottom: '1.5rem' }}>
                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: '0 0 0.5rem 0' }}>Compensation</p>
                <p style={{ fontSize: '18px', fontWeight: 600, color: '#2c2c2a', margin: 0 }}>
                  {salaryMin && salaryMax ? `${salaryMin} - ${salaryMax}` : salaryMin || salaryMax}
                </p>
              </div>
            )}
          </div>

          {/* About */}
          <div style={{ marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '18px', fontWeight: 600, margin: '0 0 1rem 0', color: '#2c2c2a' }}>About this role</h2>
            <p style={{ fontSize: '15px', lineHeight: '1.6', color: 'var(--text-primary)', whiteSpace: 'pre-wrap' }}>
              {job.description}
            </p>
          </div>

          {/* Requirements */}
          {job.skills_required && job.skills_required.length > 0 && (
            <div style={{ marginBottom: '2rem' }}>
              <h2 style={{ fontSize: '18px', fontWeight: 600, margin: '0 0 1rem 0', color: '#2c2c2a' }}>Required skills</h2>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '0.75rem' }}>
                {job.skills_required.map((skill: any, idx: number) => (
                  <div key={idx} style={{ padding: '0.75rem', background: '#F5F5F5', borderRadius: 'var(--radius)', fontSize: '14px', color: '#2c2c2a' }}>
                    ✓ {typeof skill === 'string' ? skill : skill.skill || 'Required skill'}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* CTA */}
          <div style={{ marginTop: '2rem', paddingTop: '2rem', borderTop: '0.5px solid var(--border)' }}>
            <Link href={`/apply?jobId=${job.id}`}
              style={{
                display: 'inline-block',
                padding: '14px 32px',
                background: '#185FA5',
                color: 'white',
                borderRadius: 'var(--radius)',
                fontSize: '16px',
                fontWeight: 600,
                textDecoration: 'none',
                cursor: 'pointer',
                transition: 'all 0.2s'
              }}
              onMouseEnter={(e) => { (e.target as HTMLElement).style.background = '#0C447C' }}
              onMouseLeave={(e) => { (e.target as HTMLElement).style.background = '#185FA5' }}
            >
              Apply Now →
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
