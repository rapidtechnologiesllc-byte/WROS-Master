import React, { useState, useEffect } from 'react';
import { Eye, EyeOff, Lock, Cloud } from 'lucide-react';
import { apiRequest } from '../services/api/client';

const PROVIDERS = [
  { value: 'azure', label: 'Azure', icon: '☁️', color: '#0078D4', provider: 'Azure Graph' },
  { value: 'twilio', label: 'Twilio', icon: '💬', color: '#F22F46', provider: 'Twilio (WhatsApp)' },
  { value: 'sendgrid', label: 'SendGrid', icon: '✉️', color: '#1A73E8', provider: 'SendGrid' },
];

export default function APIKeysSettings() {
  const [activeTab, setActiveTab] = useState('azure');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [showSecrets, setShowSecrets] = useState({});
  const [pageError, setPageError] = useState(null);
  const [pageSuccess, setPageSuccess] = useState(null);

  const [azureForm, setAzureForm] = useState({ tenant_id: '', client_id: '', client_secret: '' });
  const [twilioForm, setTwilioForm] = useState({ account_sid: '', auth_token: '', whatsapp_number: '' });
  const [sendgridForm, setSendgridForm] = useState({ api_key: '', from_email: '' });
  const [activeProvider, setActiveProvider] = useState(null);

  useEffect(() => {
    loadConfigurations();
  }, []);

  const loadConfigurations = async () => {
    setLoading(true);
    try {
      const response = await apiRequest('/api/v1/api-keys');
      console.log('[APIKeys] Loaded config:', response);

      if (response.azure) {
        console.log('[APIKeys] Setting Azure form:', response.azure);
        setAzureForm(response.azure);
      }
      if (response.twilio) {
        console.log('[APIKeys] Setting Twilio form:', response.twilio);
        setTwilioForm(response.twilio);
      }
      if (response.sendgrid) {
        console.log('[APIKeys] Setting SendGrid form:', response.sendgrid);
        setSendgridForm(response.sendgrid);
      }
      if (response.active_provider) {
        console.log('[APIKeys] Setting active provider:', response.active_provider);
        setActiveProvider(response.active_provider);
      }
    } catch (err) {
      console.warn('[APIKeys] Could not load credentials:', err);
    } finally {
      setLoading(false);
    }
  };

  const testProvider = async (provider) => {
    try {
      console.log('[APIKeys] Testing', provider, 'credentials');
      const response = await apiRequest('/api/v1/api-keys/test', {
        method: 'POST',
        body: JSON.stringify({ provider }),
      });
      console.log('[APIKeys] Test response:', response);
      return response.status === 'success';
    } catch (err) {
      console.error('[APIKeys] Test error:', err);
      return false;
    }
  };

  const handleSaveProvider = async (provider, formData) => {
    const required = {
      azure: ['tenant_id', 'client_id', 'client_secret'],
      twilio: ['account_sid', 'auth_token', 'whatsapp_number'],
      sendgrid: ['api_key', 'from_email'],
    };

    if (required[provider] && !required[provider].every(f => formData[f])) {
      setPageError('Please fill in all required fields');
      return;
    }

    setSaving(true);
    setPageError(null);
    setPageSuccess(null);
    try {
      console.log('[APIKeys] Saving', provider, 'credentials');
      const response = await apiRequest('/api/v1/api-keys', {
        method: 'POST',
        body: JSON.stringify({
          provider,
          [provider]: formData,
          active_provider: provider,
        }),
      });
      console.log('[APIKeys] Save response:', response);

      setPageSuccess(`${provider.charAt(0).toUpperCase() + provider.slice(1)} credentials saved successfully`);

      // Test credentials after saving
      console.log('[APIKeys] Testing credentials...');
      const testPassed = await testProvider(provider);

      if (testPassed) {
        console.log('[APIKeys] Test passed, marking as active');
        setPageSuccess(`${provider} test passed! Credentials are valid.`);
      } else {
        console.warn('[APIKeys] Test failed, credentials not activated');
        setPageError(`${provider} credentials saved but test failed. Please verify your credentials.`);
      }

      // Reload to verify save and get updated status
      await loadConfigurations();
    } catch (err) {
      console.error('[APIKeys] Save error:', err);
      setPageError(err.message || 'Failed to save credentials');
    } finally {
      setSaving(false);
    }
  };

  const toggleShowSecret = (field) => {
    setShowSecrets(prev => ({ ...prev, [field]: !prev[field] }));
  };

  const CredentialInput = ({ label, value, onChange, isSecret = false, fieldKey = null, required = false }) => {
    const showValue = fieldKey && showSecrets[fieldKey];
    return (
      <div className="mb-6">
        <label className="block text-sm font-semibold text-gray-700 mb-2 tracking-wide" style={{ fontSize: '14px', fontWeight: 600 }}>
          {label}
          {required && <span className="text-red-600 font-bold ml-1">*</span>}
        </label>
        <div className="relative">
          <input
            key={`input-${fieldKey || label}`}
            type={showValue ? 'text' : isSecret ? 'password' : 'text'}
            value={value || ''}
            onChange={(e) => {
              console.log(`[CredentialInput] ${label} changed to: ${e.target.value.substring(0, 10)}...`);
              onChange(e);
            }}
            className="w-full px-4 py-3 bg-white border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 transition text-sm placeholder:text-gray-400"
            placeholder={`Enter ${label.toLowerCase()}`}
            style={{
              fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif',
              fontSize: '14px',
              fontWeight: 400,
              letterSpacing: '0.3px'
            }}
            autoComplete="off"
          />
          {isSecret && fieldKey && (
            <button
              type="button"
              onClick={() => toggleShowSecret(fieldKey)}
              className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition"
              style={{ pointerEvents: 'auto' }}
            >
              {showSecrets[fieldKey] ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          )}
        </div>
      </div>
    );
  };

  return (
    <div style={{ fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif' }} className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 p-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-10">
          <div className="flex items-center gap-4 mb-3">
            <Cloud className="text-blue-600" size={40} strokeWidth={1.5} />
            <h1 className="text-5xl font-bold text-gray-900" style={{ fontSize: '36px', fontWeight: 700, letterSpacing: '-0.5px' }}>
              API Keys
            </h1>
          </div>
          <p className="text-gray-600 text-base" style={{ fontSize: '15px', fontWeight: 400, letterSpacing: '0.3px' }}>
            Configure delivery providers for emails and messages
          </p>
        </div>

        {/* Page-level error/success messages */}
        {pageError && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-red-800 text-sm">{pageError}</p>
          </div>
        )}
        {pageSuccess && (
          <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg">
            <p className="text-green-800 text-sm">{pageSuccess}</p>
          </div>
        )}

        {/* Provider Tabs */}
        <div className="mb-8 flex gap-3 overflow-x-auto pb-2">
          {PROVIDERS.map((p) => (
            <button
              key={p.value}
              onClick={() => setActiveTab(p.value)}
              className={`px-5 py-3 rounded-lg font-semibold text-base whitespace-nowrap transition-all ${
                activeTab === p.value
                  ? 'bg-white shadow-md text-gray-900 border-2 border-blue-500'
                  : 'bg-white/50 border-2 border-gray-200 text-gray-700 hover:bg-white/80'
              }`}
              style={{ fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif', fontSize: '14px', fontWeight: 600 }}
            >
              <span className="mr-2 text-lg">{p.icon}</span>
              {p.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-10">
          {activeTab === 'azure' && (
            <div>
              <div className="mb-8 pb-8 border-b border-gray-100">
                <div className="flex items-center gap-4 mb-2">
                  <span className="text-4xl">☁️</span>
                  <h2 className="text-3xl font-bold text-gray-900" style={{ fontSize: '28px', fontWeight: 700 }}>
                    Azure Graph
                  </h2>
                </div>
                <p className="text-gray-600 ml-20 text-base" style={{ fontSize: '15px', fontWeight: 400 }}>
                  Microsoft 365 email delivery
                </p>
                <div className="mt-4 ml-20 inline-block px-4 py-2 bg-blue-50 rounded-full">
                  <p className="text-sm font-semibold text-blue-700" style={{ fontSize: '13px', fontWeight: 600 }}>
                    {activeProvider === 'azure' ? '✓ Active' : 'Inactive'}
                  </p>
                </div>
              </div>
              <CredentialInput
                label="Tenant ID"
                value={azureForm.tenant_id}
                onChange={(e) => setAzureForm({ ...azureForm, tenant_id: e.target.value })}
                required={true}
              />
              <CredentialInput
                label="Client ID"
                value={azureForm.client_id}
                onChange={(e) => setAzureForm({ ...azureForm, client_id: e.target.value })}
                required={true}
              />
              <CredentialInput
                label="Client Secret"
                value={azureForm.client_secret}
                onChange={(e) => setAzureForm({ ...azureForm, client_secret: e.target.value })}
                isSecret
                fieldKey="azure_secret"
                required={true}
              />
              <button
                onClick={() => handleSaveProvider('azure', azureForm)}
                disabled={saving}
                className="w-full mt-8 bg-gradient-to-r from-blue-600 to-blue-700 text-white py-3 px-6 rounded-lg hover:from-blue-700 hover:to-blue-800 disabled:opacity-50 font-semibold transition text-base shadow-md hover:shadow-lg"
                style={{ fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif', fontSize: '15px', fontWeight: 600 }}
              >
                {saving ? 'Saving...' : 'Save Credentials'}
              </button>
            </div>
          )}

          {activeTab === 'twilio' && (
            <div>
              <div className="mb-8 pb-8 border-b border-gray-100">
                <div className="flex items-center gap-4 mb-2">
                  <span className="text-4xl">💬</span>
                  <h2 className="text-3xl font-bold text-gray-900" style={{ fontSize: '28px', fontWeight: 700 }}>
                    Twilio
                  </h2>
                </div>
                <p className="text-gray-600 ml-20 text-base" style={{ fontSize: '15px', fontWeight: 400 }}>
                  WhatsApp messaging delivery
                </p>
                <div className="mt-4 ml-20 inline-block px-4 py-2 bg-red-50 rounded-full">
                  <p className="text-sm font-semibold text-red-700" style={{ fontSize: '13px', fontWeight: 600 }}>
                    {activeProvider === 'twilio' ? '✓ Active' : 'Inactive'}
                  </p>
                </div>
              </div>
              <CredentialInput
                label="Account SID"
                value={twilioForm.account_sid}
                onChange={(e) => setTwilioForm({ ...twilioForm, account_sid: e.target.value })}
                required={true}
              />
              <CredentialInput
                label="Auth Token"
                value={twilioForm.auth_token}
                onChange={(e) => setTwilioForm({ ...twilioForm, auth_token: e.target.value })}
                isSecret
                fieldKey="twilio_token"
                required={true}
              />
              <CredentialInput
                label="WhatsApp Number"
                value={twilioForm.whatsapp_number}
                onChange={(e) => setTwilioForm({ ...twilioForm, whatsapp_number: e.target.value })}
                required={true}
              />
              <button
                onClick={() => handleSaveProvider('twilio', twilioForm)}
                disabled={saving}
                className="w-full mt-8 bg-gradient-to-r from-red-600 to-red-700 text-white py-3 px-6 rounded-lg hover:from-red-700 hover:to-red-800 disabled:opacity-50 font-semibold transition text-base shadow-md hover:shadow-lg"
                style={{ fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif', fontSize: '15px', fontWeight: 600 }}
              >
                {saving ? 'Saving...' : 'Save Credentials'}
              </button>
            </div>
          )}

          {activeTab === 'sendgrid' && (
            <div>
              <div className="mb-8 pb-8 border-b border-gray-100">
                <div className="flex items-center gap-4 mb-2">
                  <span className="text-4xl">✉️</span>
                  <h2 className="text-3xl font-bold text-gray-900" style={{ fontSize: '28px', fontWeight: 700 }}>
                    SendGrid
                  </h2>
                </div>
                <p className="text-gray-600 ml-20 text-base" style={{ fontSize: '15px', fontWeight: 400 }}>
                  Email delivery service
                </p>
                <div className="mt-4 ml-20 inline-block px-4 py-2 bg-blue-50 rounded-full">
                  <p className="text-sm font-semibold text-blue-700" style={{ fontSize: '13px', fontWeight: 600 }}>
                    {activeProvider === 'sendgrid' ? '✓ Active' : 'Inactive'}
                  </p>
                </div>
              </div>
              <CredentialInput
                label="API Key"
                value={sendgridForm.api_key}
                onChange={(e) => setSendgridForm({ ...sendgridForm, api_key: e.target.value })}
                isSecret
                fieldKey="sendgrid_key"
                required={true}
              />
              <CredentialInput
                label="From Email"
                value={sendgridForm.from_email}
                onChange={(e) => setSendgridForm({ ...sendgridForm, from_email: e.target.value })}
                required={true}
              />
              <button
                onClick={() => handleSaveProvider('sendgrid', sendgridForm)}
                disabled={saving}
                className="w-full mt-8 bg-gradient-to-r from-blue-600 to-cyan-600 text-white py-3 px-6 rounded-lg hover:from-blue-700 hover:to-cyan-700 disabled:opacity-50 font-semibold transition text-base shadow-md hover:shadow-lg"
                style={{ fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif', fontSize: '15px', fontWeight: 600 }}
              >
                {saving ? 'Saving...' : 'Save Credentials'}
              </button>
            </div>
          )}
        </div>

        {/* Status Footer */}
        <div className="mt-8 bg-gradient-to-r from-gray-50 to-gray-100 rounded-lg p-5 border border-gray-200">
          <div className="flex items-center gap-3 text-base text-gray-700">
            <Lock size={18} className="text-gray-400" />
            <span className="font-medium" style={{ fontSize: '14px', fontWeight: 500 }}>
              Credentials are encrypted at rest. Only you can view your API keys.
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
