import { useEffect, useState } from 'react'
import Link from 'next/link'

export default function StatusPage() {
  const [status, setStatus] = useState('submitted')

  useEffect(() => {
    const timer = setTimeout(() => {
      setStatus('in_review')
    }, 3000)
    return () => clearTimeout(timer)
  }, [])

  return (
    <div style={{ background: 'var(--surface-0)', minHeight: '100vh', padding: '2rem' }}>
      <div style={{ maxWidth: '600px', margin: '0 auto' }}>
        <div style={{ background: 'white', borderRadius: '12px', border: '0.5px solid var(--border)', padding: '2rem', textAlign: 'center' }}>
          <div style={{ fontSize: '48px', marginBottom: '1rem' }}>✅</div>
          <h1 style={{ fontSize: '24px', fontWeight: 500, marginBottom: '0.5rem' }}>Application Received!</h1>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '2rem' }}>We've received your application for Business Delivery Consultant. Our team will review your profile and get back to you soon.</p>

          <div style={{ background: 'var(--surface-1)', borderRadius: 'var(--radius)', padding: '1.5rem', marginBottom: '2rem', textAlign: 'left' }}>
            <h2 style={{ fontSize: '14px', fontWeight: 500, marginBottom: '1rem' }}>Next steps</h2>
            <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem' }}>
              <div style={{ width: '24px', height: '24px', borderRadius: '50%', background: '#0F6E56', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 500, flexShrink: 0 }}>1</div>
              <div>
                <p style={{ fontSize: '14px', fontWeight: 500, margin: '0 0 4px 0' }}>Screening review</p>
                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: 0 }}>Our hiring team will evaluate your background</p>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem' }}>
              <div style={{ width: '24px', height: '24px', borderRadius: '50%', background: '#999', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 500, flexShrink: 0 }}>2</div>
              <div>
                <p style={{ fontSize: '14px', fontWeight: 500, margin: '0 0 4px 0' }}>Manager validation</p>
                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: 0 }}>Hiring manager will review your fit for the role</p>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '1rem' }}>
              <div style={{ width: '24px', height: '24px', borderRadius: '50%', background: '#999', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 500, flexShrink: 0 }}>3</div>
              <div>
                <p style={{ fontSize: '14px', fontWeight: 500, margin: '0 0 4px 0' }}>Interview</p>
                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: 0 }}>If approved, we'll schedule an interview</p>
              </div>
            </div>
          </div>

          <div style={{ background: '#E6F1FB', borderRadius: 'var(--radius)', padding: '1rem', marginBottom: '2rem' }}>
            <p style={{ fontSize: '13px', color: '#185FA5', margin: 0 }}>💡 <strong>Tip:</strong> We'll send updates to your email. Check your spam folder if you don't see them.</p>
          </div>

          <Link href="/jobs" style={{ display: 'inline-block', padding: '12px 24px', background: '#185FA5', color: 'white', borderRadius: 'var(--radius)', fontWeight: 500, marginRight: '1rem' }} onMouseEnter={(e) => e.currentTarget.style.background = '#0C447C'} onMouseLeave={(e) => e.currentTarget.style.background = '#185FA5'}>
            Back to jobs
          </Link>
        </div>
      </div>
    </div>
  )
}
