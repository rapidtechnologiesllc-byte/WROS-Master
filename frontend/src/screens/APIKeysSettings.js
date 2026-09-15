import React, { useState, useEffect } from 'react';
import { toast } from 'react-toastify';
import { Card } from '../components/ui';
import { Check, X, AlertCircle, Eye, EyeOff } from 'lucide-react';
import { apiRequest } from '../services/api/client';

const PROVIDERS = [
  { value: 'azure', label: 'Azure Graph (Microsoft 365)', icon: '🔵' },
  { value: 'twilio', label: 'Twilio (WhatsApp)', icon: '📱' },
  { value: 'sendgrid', label: 'SendGrid (Email)', icon: '📧' },
  { value: 'stub', label: 'STUB (Testing Only)', icon: '🧪' },
];

export default function APIKeysSettings() {
  const [activeProvider, setActiveProvider] = useState('stub');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);
  const [showSecrets, setShowSecrets] = useState({});

  // Azure Form State
  const [azureForm, setAzureForm] = useState({
    tenant_id: '',
    client_id: '',
    client_secret: '',
  });

  // Twilio Form State
  const [twilioForm, setTwilioForm] = useState({
    account_sid: '',
    auth_token: '',
    whatsapp_number: '',
  });

  // SendGrid Form State
  const [sendgridForm, setSendgridForm] = useState({
    api_key: '',
    from_email: '',
  });

  // Load existing configurations on mount
  useEffect(() => {
    loadConfigurations();
  }, []);

  const loadConfigurations = async () => {
    setLoading(true);
    try {
      const response = await apiRequest('GET', '/api/v1/system/api-keys');

      if (response.azure) {
        setAzureForm({
          tenant_id: response.azure.tenant_id || '',
          client_id: response.azure.client_id || '',
          client_secret: response.azure.client_secret || '',
        });
      }

      if (response.twilio) {
        setTwilioForm({
          account_sid: response.twilio.account_sid || '',
          auth_token: response.twilio.auth_token || '',
          whatsapp_number: response.twilio.whatsapp_number || '',
        });
      }

      if (response.sendgrid) {
        setSendgridForm({
          api_key: response.sendgrid.api_key || '',
          from_email: response.sendgrid.from_email || '',
        });
      }

      if (response.active_provider) {
        setActiveProvider(response.active_provider);
      }
    } catch (err) {
      console.warn('Could not load existing credentials:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveAzure = async () => {
    if (!azureForm.tenant_id || !azureForm.client_id || !azureForm.client_secret) {
      setMessage({ type: 'error', text: 'Please fill in all Azure fields' });
      return;
    }

    setSaving(true);
    try {
      await apiRequest('POST', '/api/v1/system/api-keys', {
        provider: 'azure',
        azure: azureForm,
      });
      toast.success('Azure credentials saved');
      setMessage(null);
      if (activeProvider !== 'azure') {
        setActiveProvider('azure');
      }
    } catch (err) {
      toast.error(err.message || 'Failed to save Azure credentials');
      setMessage({ type: 'error', text: err.message || 'Failed to save' });
    } finally {
      setSaving(false);
    }
  };

  const handleSaveTwilio = async () => {
    if (!twilioForm.account_sid || !twilioForm.auth_token || !twilioForm.whatsapp_number) {
      setMessage({ type: 'error', text: 'Please fill in all Twilio fields' });
      return;
    }

    setSaving(true);
    try {
      await apiRequest('POST', '/api/v1/system/api-keys', {
        provider: 'twilio',
        twilio: twilioForm,
      });
      toast.success('Twilio credentials saved');
      setMessage(null);
      if (activeProvider !== 'twilio') {
        setActiveProvider('twilio');
      }
    } catch (err) {
      toast.error(err.message || 'Failed to save Twilio credentials');
      setMessage({ type: 'error', text: err.message || 'Failed to save' });
    } finally {
      setSaving(false);
    }
  };

  const handleSaveSendGrid = async () => {
    if (!sendgridForm.api_key || !sendgridForm.from_email) {
      setMessage({ type: 'error', text: 'Please fill in all SendGrid fields' });
      return;
    }

    setSaving(true);
    try {
      await apiRequest('POST', '/api/v1/system/api-keys', {
        provider: 'sendgrid',
        sendgrid: sendgridForm,
      });
      toast.success('SendGrid credentials saved');
      setMessage(null);
      if (activeProvider !== 'sendgrid') {
        setActiveProvider('sendgrid');
      }
    } catch (err) {
      toast.error(err.message || 'Failed to save SendGrid credentials');
      setMessage({ type: 'error', text: err.message || 'Failed to save' });
    } finally {
      setSaving(false);
    }
  };

  const handleSetProvider = async (provider) => {
    setSaving(true);
    try {
      await apiRequest('POST', '/api/v1/system/api-keys/set-provider', {
        provider,
      });
      setActiveProvider(provider);
      toast.success(`Switched to ${PROVIDERS.find(p => p.value === provider)?.label}`);
    } catch (err) {
      toast.error(err.message || 'Failed to switch provider');
    } finally {
      setSaving(false);
    }
  };

  const toggleShowSecret = (field) => {
    setShowSecrets(prev => ({
      ...prev,
      [field]: !prev[field],
    }));
  };

  const renderCredentialField = (label, value, onChange, type = 'text', isSecret = false, fieldKey = null) => {
    const showValue = fieldKey && showSecrets[fieldKey];

    return (
      <div className="mb-4">
        <label className="block text-sm font-medium text-gray-700 mb-2">{label}</label>
        <div className="relative">
          <input
            type={showValue ? 'text' : type}
            value={value}
            onChange={onChange}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500"
            placeholder={`Enter ${label.toLowerCase()}`}
          />
          {isSecret && fieldKey && (
            <button
              type="button"
              onClick={() => toggleShowSecret(fieldKey)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
            >
              {showSecrets[fieldKey] ? (
                <EyeOff size={18} />
              ) : (
                <Eye size={18} />
              )}
            </button>
          )}
        </div>
      </div>
    );
  };

  const ProviderCard = ({ provider, isActive, onSelect, children, onSave }) => (
    <Card className={`mb-4 border-2 transition-all ${isActive ? 'border-blue-500 bg-blue-50' : 'border-gray-200'}`}>
      <div className="p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <span className="text-2xl">{provider.icon}</span>
            <div>
              <h3 className="font-semibold text-gray-900">{provider.label}</h3>
              <p className="text-xs text-gray-500">
                {isActive ? 'Currently active' : 'Not active'}
              </p>
            </div>
          </div>
          <input
            type="radio"
            checked={isActive}
            onChange={() => handleSetProvider(provider.value)}
            className="w-4 h-4"
          />
        </div>

        {children}

        <div className="flex gap-2 mt-4">
          <button
            onClick={onSave}
            disabled={saving}
            className="flex-1 bg-blue-600 text-white py-2 px-4 rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save Credentials'}
          </button>
        </div>
      </div>
    </Card>
  );

  return (
    <div className="max-w-2xl mx-auto p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">API Keys Configuration</h1>
        <p className="text-gray-600">Manage credentials for email and messaging delivery providers</p>
      </div>

      {message && (
        <div className={`mb-4 p-4 rounded-lg flex gap-2 ${
          message.type === 'error' ? 'bg-red-50 text-red-700' : 'bg-blue-50 text-blue-700'
        }`}>
          <AlertCircle size={18} className="flex-shrink-0 mt-0.5" />
          <span>{message.text}</span>
        </div>
      )}

      <div className="space-y-6">
        {/* Azure Card */}
        <ProviderCard
          provider={PROVIDERS[0]}
          isActive={activeProvider === 'azure'}
          onSelect={() => handleSetProvider('azure')}
          onSave={handleSaveAzure}
        >
          {renderCredentialField(
            'Tenant ID',
            azureForm.tenant_id,
            (e) => setAzureForm({ ...azureForm, tenant_id: e.target.value }),
            'text',
            false
          )}
          {renderCredentialField(
            'Client ID',
            azureForm.client_id,
            (e) => setAzureForm({ ...azureForm, client_id: e.target.value }),
            'text',
            false
          )}
          {renderCredentialField(
            'Client Secret',
            azureForm.client_secret,
            (e) => setAzureForm({ ...azureForm, client_secret: e.target.value }),
            'password',
            true,
            'azure_secret'
          )}
        </ProviderCard>

        {/* Twilio Card */}
        <ProviderCard
          provider={PROVIDERS[1]}
          isActive={activeProvider === 'twilio'}
          onSelect={() => handleSetProvider('twilio')}
          onSave={handleSaveTwilio}
        >
          {renderCredentialField(
            'Account SID',
            twilioForm.account_sid,
            (e) => setTwilioForm({ ...twilioForm, account_sid: e.target.value }),
            'text',
            false
          )}
          {renderCredentialField(
            'Auth Token',
            twilioForm.auth_token,
            (e) => setTwilioForm({ ...twilioForm, auth_token: e.target.value }),
            'password',
            true,
            'twilio_token'
          )}
          {renderCredentialField(
            'WhatsApp Number',
            twilioForm.whatsapp_number,
            (e) => setTwilioForm({ ...twilioForm, whatsapp_number: e.target.value }),
            'tel',
            false
          )}
        </ProviderCard>

        {/* SendGrid Card */}
        <ProviderCard
          provider={PROVIDERS[2]}
          isActive={activeProvider === 'sendgrid'}
          onSelect={() => handleSetProvider('sendgrid')}
          onSave={handleSaveSendGrid}
        >
          {renderCredentialField(
            'API Key',
            sendgridForm.api_key,
            (e) => setSendgridForm({ ...sendgridForm, api_key: e.target.value }),
            'password',
            true,
            'sendgrid_key'
          )}
          {renderCredentialField(
            'From Email',
            sendgridForm.from_email,
            (e) => setSendgridForm({ ...sendgridForm, from_email: e.target.value }),
            'email',
            false
          )}
        </ProviderCard>

        {/* STUB Card */}
        <ProviderCard
          provider={PROVIDERS[3]}
          isActive={activeProvider === 'stub'}
          onSelect={() => handleSetProvider('stub')}
          onSave={() => {
            setActiveProvider('stub');
            toast.success('Switched to STUB mode (testing)');
          }}
        >
          <div className="text-sm text-gray-600">
            <p className="mb-2">STUB mode logs all emails and messages to the database instead of sending them.</p>
            <p>Use this for development and testing.</p>
          </div>
        </ProviderCard>
      </div>
    </div>
  );
}
