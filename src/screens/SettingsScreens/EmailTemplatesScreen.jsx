import React, { useState, useEffect } from 'react'
import styles from './EmailTemplatesScreen.module.css'

const STAGES = [
  { key: 'screening', label: 'Screening', icon: '📋' },
  { key: 'interview', label: 'Interview', icon: '🎯' },
  { key: 'offer', label: 'Offer', icon: '🎉' },
  { key: 'hired', label: 'Hired', icon: '✅' },
  { key: 'rejected', label: 'Rejected', icon: '❌' },
]

export default function EmailTemplatesScreen() {
  const [templates, setTemplates] = useState({})
  const [selectedStage, setSelectedStage] = useState('screening')
  const [editing, setEditing] = useState(false)
  const [subject, setSubject] = useState('')
  const [bodyHtml, setBodyHtml] = useState('')
  const [loading, setLoading] = useState(false)
  const [preview, setPreview] = useState(false)
  const [previewData, setPreviewData] = useState(null)
  const [candidates, setCandidates] = useState([])
  const [selectedCandidate, setSelectedCandidate] = useState('')

  useEffect(() => {
    fetchTemplates()
    fetchCandidates()
  }, [])

  useEffect(() => {
    const template = templates[selectedStage]
    if (template) {
      setSubject(template.subject || '')
      setBodyHtml(template.body_html || '')
    }
  }, [selectedStage, templates])

  const fetchTemplates = async () => {
    try {
      const response = await fetch('/api/v1/email-templates', {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
      })
      const data = await response.json()
      const templateMap = {}
      data.templates?.forEach(t => {
        templateMap[t.stage] = t
      })
      setTemplates(templateMap)
    } catch (error) {
      console.error('Failed to fetch templates:', error)
    }
  }

  const fetchCandidates = async () => {
    try {
      const response = await fetch('/api/v1/candidates', {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
      })
      const data = await response.json()
      setCandidates(data.candidates || [])
      if (data.candidates?.length > 0) {
        setSelectedCandidate(data.candidates[0].candidate_id)
      }
    } catch (error) {
      console.error('Failed to fetch candidates:', error)
    }
  }

  const handleSave = async () => {
    setLoading(true)
    try {
      const response = await fetch(`/api/v1/email-templates/${selectedStage}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        },
        body: JSON.stringify({
          subject,
          body_html: bodyHtml
        })
      })

      if (response.ok) {
        alert('Template saved successfully!')
        setEditing(false)
        await fetchTemplates()
      }
    } catch (error) {
      console.error('Failed to save template:', error)
      alert('Failed to save template')
    } finally {
      setLoading(false)
    }
  }

  const handlePreview = async () => {
    if (!selectedCandidate) {
      alert('Please select a candidate to preview')
      return
    }

    try {
      const candidate = candidates.find(c => c.candidate_id === selectedCandidate)
      if (!candidate) return

      const candidateName = encodeURIComponent(candidate.candidate_name || 'Candidate')
      const jobTitle = encodeURIComponent(candidate.candidate_job_title || 'Position')

      const response = await fetch(
        `/api/v1/email-templates/${selectedStage}/preview?candidate_name=${candidateName}&job_title=${jobTitle}`,
        {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
        }
      )
      const data = await response.json()
      setPreviewData(data)
      setPreview(true)
    } catch (error) {
      console.error('Failed to preview template:', error)
      alert('Failed to preview template')
    }
  }

  const stage = templates[selectedStage]

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h1>Email Templates</h1>
        <p>Manage email templates for candidate stage progression</p>
      </div>

      <div style={{ marginBottom: '20px', display: 'flex', gap: '20px', alignItems: 'center' }}>
        <label style={{ fontWeight: '600', minWidth: '120px' }}>Preview with Candidate:</label>
        <select
          value={selectedCandidate}
          onChange={(e) => setSelectedCandidate(e.target.value)}
          style={{
            padding: '10px 12px',
            borderRadius: '6px',
            border: '1px solid var(--color-border)',
            backgroundColor: 'var(--color-bg-primary)',
            color: 'var(--color-text-primary)',
            fontSize: '14px',
            minWidth: '300px',
            maxWidth: '100%'
          }}
        >
          <option value="">-- Select a candidate --</option>
          {candidates.map(c => (
            <option key={c.candidate_id} value={c.candidate_id}>
              {c.candidate_name} - {c.candidate_job_title}
            </option>
          ))}
        </select>
      </div>

      <div className={styles.layout}>
        {/* Sidebar - Stage Selection */}
        <div className={styles.sidebar}>
          <h3>Stages</h3>
          {STAGES.map(s => (
            <button
              key={s.key}
              className={`${styles.stageBtn} ${selectedStage === s.key ? styles.active : ''}`}
              onClick={() => setSelectedStage(s.key)}
            >
              <span className={styles.icon}>{s.icon}</span>
              <span>{s.label}</span>
            </button>
          ))}
        </div>

        {/* Main Content */}
        <div className={styles.content}>
          {stage ? (
            <>
              <div className={styles.templateInfo}>
                <div className={styles.stageName}>
                  {STAGES.find(s => s.key === selectedStage)?.label} Email Template
                </div>
                {!editing ? (
                  <div className={styles.viewMode}>
                    <div className={styles.field}>
                      <label>Subject Line</label>
                      <div className={styles.value}>{subject}</div>
                    </div>
                    <div className={styles.field}>
                      <label>Email Body</label>
                      <div className={styles.emailPreview} dangerouslySetInnerHTML={{ __html: bodyHtml }} />
                    </div>
                    <div className={styles.actions}>
                      <button className={styles.btnPrimary} onClick={() => setEditing(true)}>
                        ✏️ Edit Template
                      </button>
                      <button className={styles.btnSecondary} onClick={handlePreview}>
                        👁️ Preview
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className={styles.editMode}>
                    <div className={styles.field}>
                      <label>Subject Line</label>
                      <input
                        type="text"
                        value={subject}
                        onChange={(e) => setSubject(e.target.value)}
                        placeholder="E.g., Interview Invitation for [Job Title] - BlitzenX"
                      />
                      <small>Use [Candidate Name] and [Job Title] for placeholders</small>
                    </div>
                    <div className={styles.field}>
                      <label>Email Body (HTML)</label>
                      <textarea
                        value={bodyHtml}
                        onChange={(e) => setBodyHtml(e.target.value)}
                        rows={15}
                        placeholder="Enter HTML email content..."
                      />
                      <small>HTML email template. Use [Candidate Name] and [Job Title] for placeholders</small>
                    </div>
                    <div className={styles.actions}>
                      <button className={styles.btnPrimary} onClick={handleSave} disabled={loading}>
                        {loading ? 'Saving...' : '💾 Save Template'}
                      </button>
                      <button className={styles.btnSecondary} onClick={() => setEditing(false)}>
                        ❌ Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className={styles.noTemplate}>
              <p>No template found for this stage</p>
            </div>
          )}
        </div>
      </div>

      {/* Preview Modal */}
      {preview && previewData && (
        <div className={styles.modal} onClick={() => setPreview(false)}>
          <div className={styles.modalContent} onClick={(e) => e.stopPropagation()}>
            <button className={styles.closeBtn} onClick={() => setPreview(false)}>✕</button>
            <h2>Email Preview</h2>
            <div className={styles.previewSubject}>
              <strong>Subject:</strong> {previewData.subject}
            </div>
            <div className={styles.previewBody} dangerouslySetInnerHTML={{ __html: previewData.body_html }} />
          </div>
        </div>
      )}
    </div>
  )
}
