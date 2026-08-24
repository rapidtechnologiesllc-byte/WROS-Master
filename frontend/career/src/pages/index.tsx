import { useEffect } from 'react'
import { useRouter } from 'next/router'

export default function IndexPage() {
  const router = useRouter()

  useEffect(() => {
    // Redirect to jobs page
    router.replace('/jobs')
  }, [router])

  return (
    <div style={{ display: 'flex', height: '100vh', alignItems: 'center', justifyContent: 'center', background: 'var(--surface-0)' }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: '48px', marginBottom: '1rem' }}>🚀</div>
        <p style={{ fontSize: '16px', color: 'var(--text-secondary)' }}>Redirecting to careers...</p>
      </div>
    </div>
  )
}
