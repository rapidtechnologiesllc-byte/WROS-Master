import React, { useState } from 'react';
import { apiRequest } from '../services/api';

/**
 * LinkedIn Candidate Import Screen
 *
 * WHY IT'S NOT WORKING:
 * 1. Apollo MCP OAuth not configured - requires setup at claude.ai/settings/connectors
 * 2. Missing /candidate/import/linkedin endpoint - not wired in backend
 * 3. No LinkedIn auth flow - OAuth redirect not implemented
 * 4. No WhatsApp consent capture - LinkedIn profiles don't imply consent
 * 5. Missing candidate list integration - results not linked to workflow
 */
export default function LinkedInImportScreen() {
  const [linkedinUrl, setLinkedinUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [candidate, setCandidate] = useState(null);

  const handleImport = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setLoading(true);

    try {
      const response = await apiRequest('/candidate/import/linkedin', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ linkedin_url: linkedinUrl }),
      });

      if (response.status === 'success') {
        setCandidate(response.data);
        setSuccess(`Candidate imported: ${response.data.candidateFirstName} ${response.data.candidateLastName}`);
        setLinkedinUrl('');
      } else if (response.status === 'error') {
        setError(response.message || 'Failed to import candidate');
      }
    } catch (err) {
      setError(`Import failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="linkedin-import-container" style={{ padding: '20px', maxWidth: '600px' }}>
      <h2>Import Candidate from LinkedIn</h2>

      {/* BLOCKER NOTICE */}
      <div style={{
        backgroundColor: '#fff3cd',
        border: '1px solid #ffc107',
        padding: '15px',
        borderRadius: '4px',
        marginBottom: '20px'
      }}>
        <h4>🚨 Feature Not Yet Available</h4>
        <p>LinkedIn import requires Apollo.io OAuth configuration. This needs to be completed:</p>
        <ol>
          <li>Visit claude.ai/settings/connectors</li>
          <li>Set up Apollo.io MCP connection</li>
          <li>Deploy backend /candidate/import/linkedin endpoint</li>
          <li>Implement WhatsApp consent flow</li>
        </ol>
      </div>

      <form onSubmit={handleImport}>
        <div style={{ marginBottom: '15px' }}>
          <label htmlFor="linkedin-url" style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
            LinkedIn Profile URL
          </label>
          <input
            id="linkedin-url"
            type="text"
            placeholder="https://linkedin.com/in/john-doe or https://linkedin.com/in/john-doe/"
            value={linkedinUrl}
            onChange={(e) => setLinkedinUrl(e.target.value)}
            disabled={loading}
            style={{
              width: '100%',
              padding: '10px',
              border: '1px solid #ddd',
              borderRadius: '4px',
              fontSize: '14px'
            }}
          />
          <small style={{ color: '#666', marginTop: '5px', display: 'block' }}>
            Paste the full LinkedIn profile URL. The candidate must have "Open to Work" status.
          </small>
        </div>

        <button
          type="submit"
          disabled={!linkedinUrl || loading}
          style={{
            padding: '10px 20px',
            backgroundColor: '#007bff',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: loading ? 'not-allowed' : 'pointer',
            opacity: (!linkedinUrl || loading) ? 0.5 : 1,
            fontSize: '14px'
          }}
        >
          {loading ? 'Importing...' : 'Import Candidate'}
        </button>
      </form>

      {error && (
        <div style={{
          marginTop: '20px',
          padding: '12px',
          backgroundColor: '#f8d7da',
          color: '#721c24',
          border: '1px solid #f5c6cb',
          borderRadius: '4px'
        }}>
          ❌ {error}
        </div>
      )}

      {success && (
        <div style={{
          marginTop: '20px',
          padding: '12px',
          backgroundColor: '#d4edda',
          color: '#155724',
          border: '1px solid #c3e6cb',
          borderRadius: '4px'
        }}>
          ✅ {success}
        </div>
      )}

      {candidate && (
        <div style={{
          marginTop: '20px',
          padding: '15px',
          backgroundColor: '#f0f0f0',
          borderRadius: '4px'
        }}>
          <h4>Candidate Details</h4>
          <p><strong>Name:</strong> {candidate.candidateFirstName} {candidate.candidateLastName}</p>
          <p><strong>Email:</strong> {candidate.candidateEmail}</p>
          {candidate.candidateMobile && <p><strong>Phone:</strong> {candidate.candidateMobile}</p>}
          {candidate.candidateSource && <p><strong>Source:</strong> LinkedIn</p>}
          <button
            onClick={() => window.location.href = `/candidate/${candidate.candidateID}`}
            style={{
              marginTop: '10px',
              padding: '8px 15px',
              backgroundColor: '#28a745',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            View Full Profile
          </button>
        </div>
      )}
    </div>
  );
}
