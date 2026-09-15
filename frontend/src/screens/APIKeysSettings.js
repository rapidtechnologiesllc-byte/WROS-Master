import React, { useState, useEffect } from 'react';
import { toast } from 'react-toastify';
import { Eye, EyeOff, Lock, Cloud } from 'lucide-react';
import { apiRequest } from '../services/api/client';

const PROVIDERS = [
  { value: 'azure', label: 'Azure', icon: '☁️', color: '#0078D4', provider: 'Azure Graph' },
  { value: 'twilio', label: 'Twilio', icon: '💬', color: '#F22F46', provider: 'Twilio (WhatsApp)' },
  { value: 'sendgrid', label: 'SendGrid', icon: '✉️', color: '#1A73E8', provider: 'SendGrid' },
  { value: 'stub', label: 'STUB', icon: '🧪', color: '#8B5CF6', provider: 'Test Mode' },
];

export default function APIKeysSettings() {
  const [activeTab, setActiveTab] = useState('azure');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [showSecrets, setShowSecrets] = useState({});

  const [azureForm, setAzureForm] = useState({ tenant_id: '', client_id: '', client_secret: '' });
  const [twilioForm, setTwilioForm] = useState({ account_sid: '', auth_token: '', whatsapp_number: '' });
  const [sendgridForm, setSendgridForm] = useState({ api_key: '', from_email: '' });
  const [activeProvider, setActiveProvider] = useState('stub');

  useEffect(() => {
    loadConfigurations();
  }, []);

  const loadConfigurations = async () => {
    setLoading(true);
    try {
      const response = await apiRequest('GET', '/api/v1/api-keys');
      if (response.azure) setAzureForm(response.azure);
      if (response.twilio) setTwilioForm(response.twilio);
      if (response.sendgrid) setSendgridForm(response.sendgrid);
      if (response.active_provider) setActiveProvider(response.active_provider);
    } catch (err) {
      console.warn('Could not load credentials:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveProvider = async (provider, formData) => {
    const required = {
      azure: ['tenant_id', 'client_id', 'client_secret'],
      twilio: ['account_sid', 'auth_token', 'whatsapp_number'],
      sendgrid: ['api_key', 'from_email'],
    };

    if (required[provider] && !required[provider].every(f => formData[f])) {
      toast.error('Please fill in all required fields');
      return;
    }

    setSaving(true);
    try {
      await apiRequest('POST', '/api/v1/api-keys', {
        provider,
        [provider]: formData,
      });
      toast.success(`${provider.charAt(0).toUpperCase() + provider.slice(1)} credentials saved`);
      if (activeProvider !== provider) setActiveProvider(provider);
    } catch (err) {
      toast.error(err.message || 'Failed to save credentials');
    } finally {
      setSaving(false);
    }
  };

  const toggleShowSecret = (field) => {
    setShowSecrets(prev => ({ ...prev, [field]: !prev[field] }));
  };

  const CredentialInput = ({ label, value, onChange, isSecret = false, fieldKey = null }) => {
    const showValue = fieldKey && showSecrets[fieldKey];
    return (
      <div className="mb-4">
        <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wide mb-2">
          {label}
        </label>
        <div className="relative">
          <input
            type={showValue ? 'text' : isSecret ? 'password' : 'text'}
            value={value}
            onChange={onChange}
            className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white transition text-sm"
            placeholder={`Enter ${label.toLowerCase()}`}
          />
          {isSecret && fieldKey && (
            <button
              type="button"
              onClick={() => toggleShowSecret(fieldKey)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition"
            >
              {showSecrets[fieldKey] ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 p-6">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <Cloud className="text-blue-600" size={28} />
            <h1 className="text-3xl font-bold text-gray-900">API Keys</h1>
          </div>
          <p className="text-gray-600 text-sm">Configure delivery providers for emails and messages</p>
        </div>

        {/* Provider Tabs */}
        <div className="mb-6 flex gap-2 overflow-x-auto pb-2">
          {PROVIDERS.map((p) => (
            <button
              key={p.value}
              onClick={() => setActiveTab(p.value)}
              className={`px-4 py-2.5 rounded-lg font-medium text-sm whitespace-nowrap transition-all ${
                activeTab === p.value
                  ? 'bg-white shadow-md text-gray-900 border-2 border-blue-500'
                  : 'bg-white/50 border border-gray-200 text-gray-600 hover:bg-white/80'
              }`}
            >
              <span className="mr-2">{p.icon}</span>
              {p.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
          {activeTab === 'azure' && (
            <div>
              <div className="mb-6">
                <div className="flex items-center gap-3 mb-1">
                  <span className="text-3xl">☁️</span>
                  <h2 className="text-xl font-bold text-gray-900">Azure Graph</h2>
                </div>
                <p className="text-sm text-gray-500">Microsoft 365 email delivery</p>
                <div className="mt-3 inline-block px-3 py-1 bg-blue-50 rounded-full">
                  <p className="text-xs font-medium text-blue-700">
                    {activeProvider === 'azure' ? '✓ Active' : 'Inactive'}
                  </p>
                </div>
              </div>
              <CredentialInput
                label="Tenant ID"
                value={azureForm.tenant_id}
                onChange={(e) => setAzureForm({ ...azureForm, tenant_id: e.target.value })}
              />
              <CredentialInput
                label="Client ID"
                value={azureForm.client_id}
                onChange={(e) => setAzureForm({ ...azureForm, client_id: e.target.value })}
              />
              <CredentialInput
                label="Client Secret"
                value={azureForm.client_secret}
                onChange={(e) => setAzureForm({ ...azureForm, client_secret: e.target.value })}
                isSecret
                fieldKey="azure_secret"
              />
              <button
                onClick={() => handleSaveProvider('azure', azureForm)}
                disabled={saving}
                className="w-full mt-6 bg-gradient-to-r from-blue-600 to-blue-700 text-white py-2.5 px-4 rounded-lg hover:from-blue-700 hover:to-blue-800 disabled:opacity-50 font-medium transition text-sm"
              >
                {saving ? 'Saving...' : 'Save Credentials'}
              </button>
            </div>
          )}

          {activeTab === 'twilio' && (
            <div>
              <div className="mb-6">
                <div className="flex items-center gap-3 mb-1">
                  <span className="text-3xl">💬</span>
                  <h2 className="text-xl font-bold text-gray-900">Twilio</h2>
                </div>
                <p className="text-sm text-gray-500">WhatsApp messaging delivery</p>
                <div className="mt-3 inline-block px-3 py-1 bg-red-50 rounded-full">
                  <p className="text-xs font-medium text-red-700">
                    {activeProvider === 'twilio' ? '✓ Active' : 'Inactive'}
                  </p>
                </div>
              </div>
              <CredentialInput
                label="Account SID"
                value={twilioForm.account_sid}
                onChange={(e) => setTwilioForm({ ...twilioForm, account_sid: e.target.value })}
              />
              <CredentialInput
                label="Auth Token"
                value={twilioForm.auth_token}
                onChange={(e) => setTwilioForm({ ...twilioForm, auth_token: e.target.value })}
                isSecret
                fieldKey="twilio_token"
              />
              <CredentialInput
                label="WhatsApp Number"
                value={twilioForm.whatsapp_number}
                onChange={(e) => setTwilioForm({ ...twilioForm, whatsapp_number: e.target.value })}
              />
              <button
                onClick={() => handleSaveProvider('twilio', twilioForm)}
                disabled={saving}
                className="w-full mt-6 bg-gradient-to-r from-red-600 to-red-700 text-white py-2.5 px-4 rounded-lg hover:from-red-700 hover:to-red-800 disabled:opacity-50 font-medium transition text-sm"
              >
                {saving ? 'Saving...' : 'Save Credentials'}
              </button>
            </div>
          )}

          {activeTab === 'sendgrid' && (
            <div>
              <div className="mb-6">
                <div className="flex items-center gap-3 mb-1">
                  <span className="text-3xl">✉️</span>
                  <h2 className="text-xl font-bold text-gray-900">SendGrid</h2>
                </div>
                <p className="text-sm text-gray-500">Email delivery service</p>
                <div className="mt-3 inline-block px-3 py-1 bg-blue-50 rounded-full">
                  <p className="text-xs font-medium text-blue-700">
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
              />
              <CredentialInput
                label="From Email"
                value={sendgridForm.from_email}
                onChange={(e) => setSendgridForm({ ...sendgridForm, from_email: e.target.value })}
              />
              <button
                onClick={() => handleSaveProvider('sendgrid', sendgridForm)}
                disabled={saving}
                className="w-full mt-6 bg-gradient-to-r from-blue-600 to-cyan-600 text-white py-2.5 px-4 rounded-lg hover:from-blue-700 hover:to-cyan-700 disabled:opacity-50 font-medium transition text-sm"
              >
                {saving ? 'Saving...' : 'Save Credentials'}
              </button>
            </div>
          )}

          {activeTab === 'stub' && (
            <div>
              <div className="mb-6">
                <div className="flex items-center gap-3 mb-1">
                  <span className="text-3xl">🧪</span>
                  <h2 className="text-xl font-bold text-gray-900">Test Mode</h2>
                </div>
                <p className="text-sm text-gray-500">Development & testing</p>
                <div className="mt-3 inline-block px-3 py-1 bg-purple-50 rounded-full">
                  <p className="text-xs font-medium text-purple-700">
                    {activeProvider === 'stub' ? '✓ Active' : 'Inactive'}
                  </p>
                </div>
              </div>
              <div className="bg-purple-50 border border-purple-200 rounded-lg p-4 mb-6">
                <p className="text-sm text-purple-900">
                  <strong>STUB mode</strong> logs all emails and messages to the database instead of actually sending them. Perfect for development and testing.
                </p>
              </div>
              <button
                onClick={() => setActiveProvider('stub')}
                className="w-full bg-gradient-to-r from-purple-600 to-purple-700 text-white py-2.5 px-4 rounded-lg hover:from-purple-700 hover:to-purple-800 font-medium transition text-sm"
              >
                {activeProvider === 'stub' ? '✓ Currently Active' : 'Activate Test Mode'}
              </button>
            </div>
          )}
        </div>

        {/* Status Footer */}
        <div className="mt-6 bg-gradient-to-r from-gray-50 to-gray-100 rounded-lg p-4 border border-gray-200">
          <div className="flex items-center gap-2 text-sm text-gray-700">
            <Lock size={16} className="text-gray-400" />
            <span>Credentials are encrypted at rest. Only you can view your API keys.</span>
          </div>
        </div>
      </div>
    </div>
  );
}
