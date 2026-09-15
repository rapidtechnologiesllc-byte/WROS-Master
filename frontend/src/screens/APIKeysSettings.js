/**
 * API Keys Settings Screen
 * ========================
 *
 * Manage credentials for email/messaging delivery providers:
 * - Azure Graph (Microsoft 365)
 * - Twilio (WhatsApp)
 * - SendGrid (Email)
 * - STUB (Testing/Development)
 *
 * Features:
 * - Add/update provider credentials (securely encrypted)
 * - Test connections before saving
 * - Switch between providers
 * - View configuration status without exposing secrets
 * - Audit trail of changes
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  Tabs,
  Tab,
  TextField,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Alert,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Radio,
  RadioGroup,
  FormControlLabel,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material';
import { apiRequest } from '../services/api';

const PROVIDERS = [
  { value: 'azure', label: 'Azure Graph (Microsoft 365)', icon: '🔵' },
  { value: 'twilio', label: 'Twilio (WhatsApp)', icon: '📱' },
  { value: 'sendgrid', label: 'SendGrid (Email)', icon: '📧' },
  { value: 'stub', label: 'STUB (Testing Only)', icon: '🧪' },
];

export default function APIKeysSettings() {
  // ────────────────────────────────────────────────────────────────
  // State
  // ────────────────────────────────────────────────────────────────

  const [activeTab, setActiveTab] = useState(0);
  const [activeProvider, setActiveProvider] = useState('stub');
  const [configurations, setConfigurations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState({});
  const [message, setMessage] = useState(null);
  const [messageType, setMessageType] = useState('info');
  const [testDialogOpen, setTestDialogOpen] = useState(false);
  const [testProvider, setTestProvider] = useState(null);
  const [testResult, setTestResult] = useState(null);

  // ────── Azure Form State ──────────────────────────────────────
  const [azureForm, setAzureForm] = useState({
    tenant_id: '',
    client_id: '',
    client_secret: '',
  });

  // ────── Twilio Form State ──────────────────────────────────────
  const [twilioForm, setTwilioForm] = useState({
    account_sid: '',
    auth_token: '',
    whatsapp_number: '',
  });

  // ────── SendGrid Form State ──────────────────────────────────────
  const [sendgridForm, setSendgridForm] = useState({
    api_key: '',
    from_email: '',
  });

  // ────────────────────────────────────────────────────────────────
  // Effects
  // ────────────────────────────────────────────────────────────────

  useEffect(() => {
    loadConfigurations();
  }, []);

  // ────────────────────────────────────────────────────────────────
  // API Calls
  // ────────────────────────────────────────────────────────────────

  const loadConfigurations = async () => {
    try {
      setLoading(true);
      const response = await apiRequest('/api/v1/api-keys', { method: 'GET' });
      setConfigurations(response.providers || []);
      setActiveProvider(response.active_provider || 'stub');
    } catch (error) {
      setMessage(`Failed to load configurations: ${error.message}`);
      setMessageType('error');
    } finally {
      setLoading(false);
    }
  };

  const saveCredentials = async () => {
    try {
      setSaving(true);
      setMessage(null);

      // Build request with only filled-in providers
      const request = {
        active_provider: activeProvider,
      };

      // Only include providers with values
      if (azureForm.tenant_id || azureForm.client_id || azureForm.client_secret) {
        request.azure = azureForm;
      }
      if (twilioForm.account_sid || twilioForm.auth_token || twilioForm.whatsapp_number) {
        request.twilio = twilioForm;
      }
      if (sendgridForm.api_key || sendgridForm.from_email) {
        request.sendgrid = sendgridForm;
      }

      // Validate at least one provider filled
      if (!request.azure && !request.twilio && !request.sendgrid) {
        setMessage('Please fill in credentials for at least one provider');
        setMessageType('warning');
        return;
      }

      const response = await apiRequest('/api/v1/api-keys', {
        method: 'POST',
        body: request,
      });

      setMessage(`${response.message} (${response.saved_providers?.join(', ')})`);
      setMessageType('success');

      // Clear forms on successful save
      setAzureForm({ tenant_id: '', client_id: '', client_secret: '' });
      setTwilioForm({ account_sid: '', auth_token: '', whatsapp_number: '' });
      setSendgridForm({ api_key: '', from_email: '' });

      // Reload configurations
      await loadConfigurations();
    } catch (error) {
      setMessage(`Failed to save credentials: ${error.message}`);
      setMessageType('error');
    } finally {
      setSaving(false);
    }
  };

  const testConnection = async (provider) => {
    try {
      setTesting({ ...testing, [provider]: true });
      const response = await apiRequest('/api/v1/api-keys/test', {
        method: 'POST',
        body: { provider },
      });

      setTestResult({
        provider,
        status: response.status,
        message: response.message,
        details: response.details,
      });
    } catch (error) {
      setTestResult({
        provider,
        status: 'failed',
        message: error.message,
      });
    } finally {
      setTesting({ ...testing, [provider]: false });
    }
  };

  const openTestDialog = (provider) => {
    setTestProvider(provider);
    setTestDialogOpen(true);
    testConnection(provider);
  };

  // ────────────────────────────────────────────────────────────────
  // Render Helpers
  // ────────────────────────────────────────────────────────────────

  const renderAzureForm = () => (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <TextField
        label="Tenant ID"
        value={azureForm.tenant_id}
        onChange={(e) => setAzureForm({ ...azureForm, tenant_id: e.target.value })}
        placeholder="your-tenant-id"
        fullWidth
      />
      <TextField
        label="Client ID"
        value={azureForm.client_id}
        onChange={(e) => setAzureForm({ ...azureForm, client_id: e.target.value })}
        placeholder="your-client-id"
        fullWidth
      />
      <TextField
        label="Client Secret"
        type="password"
        value={azureForm.client_secret}
        onChange={(e) => setAzureForm({ ...azureForm, client_secret: e.target.value })}
        placeholder="your-client-secret"
        fullWidth
      />
      <Button
        variant="outlined"
        onClick={() => openTestDialog('azure')}
        disabled={testing.azure}
      >
        {testing.azure ? <CircularProgress size={20} /> : 'Test Azure Connection'}
      </Button>
    </Box>
  );

  const renderTwilioForm = () => (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <TextField
        label="Account SID"
        value={twilioForm.account_sid}
        onChange={(e) => setTwilioForm({ ...twilioForm, account_sid: e.target.value })}
        placeholder="your-account-sid"
        fullWidth
      />
      <TextField
        label="Auth Token"
        type="password"
        value={twilioForm.auth_token}
        onChange={(e) => setTwilioForm({ ...twilioForm, auth_token: e.target.value })}
        placeholder="your-auth-token"
        fullWidth
      />
      <TextField
        label="WhatsApp Number"
        value={twilioForm.whatsapp_number}
        onChange={(e) => setTwilioForm({ ...twilioForm, whatsapp_number: e.target.value })}
        placeholder="+1234567890"
        fullWidth
      />
      <Button
        variant="outlined"
        onClick={() => openTestDialog('twilio')}
        disabled={testing.twilio}
      >
        {testing.twilio ? <CircularProgress size={20} /> : 'Test Twilio Connection'}
      </Button>
    </Box>
  );

  const renderSendGridForm = () => (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <TextField
        label="API Key"
        type="password"
        value={sendgridForm.api_key}
        onChange={(e) => setSendgridForm({ ...sendgridForm, api_key: e.target.value })}
        placeholder="your-sendgrid-api-key"
        fullWidth
      />
      <TextField
        label="From Email"
        type="email"
        value={sendgridForm.from_email}
        onChange={(e) => setSendgridForm({ ...sendgridForm, from_email: e.target.value })}
        placeholder="noreply@blitzenx.com"
        fullWidth
      />
      <Button
        variant="outlined"
        onClick={() => openTestDialog('sendgrid')}
        disabled={testing.sendgrid}
      >
        {testing.sendgrid ? <CircularProgress size={20} /> : 'Test SendGrid Connection'}
      </Button>
    </Box>
  );

  const renderConfigurationTable = () => (
    <TableContainer component={Paper} sx={{ marginTop: 3 }}>
      <Table>
        <TableHead sx={{ backgroundColor: '#f5f5f5' }}>
          <TableRow>
            <TableCell><strong>Provider</strong></TableCell>
            <TableCell><strong>Status</strong></TableCell>
            <TableCell><strong>Active</strong></TableCell>
            <TableCell><strong>Last Tested</strong></TableCell>
            <TableCell><strong>Result</strong></TableCell>
            <TableCell><strong>Actions</strong></TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {configurations.map((config) => (
            <TableRow key={config.provider}>
              <TableCell>{config.provider.toUpperCase()}</TableCell>
              <TableCell>
                {config.status === 'configured' ? (
                  <span style={{ color: 'green' }}>✓ Configured</span>
                ) : (
                  <span style={{ color: 'orange' }}>⚠ Not Configured</span>
                )}
              </TableCell>
              <TableCell>
                <Radio
                  checked={activeProvider === config.provider}
                  onChange={() => setActiveProvider(config.provider)}
                />
              </TableCell>
              <TableCell>
                {config.last_tested_at
                  ? new Date(config.last_tested_at).toLocaleDateString()
                  : 'Never'}
              </TableCell>
              <TableCell>
                {config.last_tested_status === 'success' && (
                  <span style={{ color: 'green' }}>✓ Success</span>
                )}
                {config.last_tested_status === 'failed' && (
                  <span style={{ color: 'red' }}>✗ Failed</span>
                )}
                {!config.last_tested_status && (
                  <span style={{ color: 'gray' }}>-</span>
                )}
              </TableCell>
              <TableCell>
                <Button
                  size="small"
                  onClick={() => openTestDialog(config.provider)}
                  disabled={testing[config.provider]}
                >
                  Test
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );

  // ────────────────────────────────────────────────────────────────
  // Main Render
  // ────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '400px' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ padding: 3 }}>
      {/* Header */}
      <Box sx={{ marginBottom: 3 }}>
        <h1>API Keys Configuration</h1>
        <p>Manage credentials for email and messaging delivery providers</p>
      </Box>

      {/* Messages */}
      {message && (
        <Alert severity={messageType} sx={{ marginBottom: 2 }} onClose={() => setMessage(null)}>
          {message}
        </Alert>
      )}

      {/* Active Provider Section */}
      <Card sx={{ marginBottom: 3 }}>
        <CardContent>
          <h3>📌 Active Delivery Provider</h3>
          <p>Currently selected: <strong>{activeProvider.toUpperCase()}</strong></p>
          <RadioGroup
            row
            value={activeProvider}
            onChange={(e) => setActiveProvider(e.target.value)}
          >
            {PROVIDERS.map((provider) => (
              <FormControlLabel
                key={provider.value}
                value={provider.value}
                control={<Radio />}
                label={`${provider.icon} ${provider.label}`}
              />
            ))}
          </RadioGroup>
        </CardContent>
      </Card>

      {/* Credentials Form */}
      <Card sx={{ marginBottom: 3 }}>
        <CardContent>
          <h3>🔐 Add/Update Credentials</h3>

          <Tabs
            value={activeTab}
            onChange={(e, newValue) => setActiveTab(newValue)}
            sx={{ marginBottom: 2, borderBottom: '1px solid #ddd' }}
          >
            <Tab label="🔵 Azure Graph" value={0} />
            <Tab label="📱 Twilio" value={1} />
            <Tab label="📧 SendGrid" value={2} />
          </Tabs>

          {/* Tab Panels */}
          {activeTab === 0 && renderAzureForm()}
          {activeTab === 1 && renderTwilioForm()}
          {activeTab === 2 && renderSendGridForm()}

          {/* Save Button */}
          <Box sx={{ marginTop: 3, display: 'flex', gap: 2 }}>
            <Button
              variant="contained"
              color="primary"
              onClick={saveCredentials}
              disabled={saving}
            >
              {saving ? <CircularProgress size={20} /> : 'Save Credentials'}
            </Button>
            <Button
              variant="outlined"
              onClick={() => {
                setAzureForm({ tenant_id: '', client_id: '', client_secret: '' });
                setTwilioForm({ account_sid: '', auth_token: '', whatsapp_number: '' });
                setSendgridForm({ api_key: '', from_email: '' });
              }}
            >
              Clear Forms
            </Button>
          </Box>
        </CardContent>
      </Card>

      {/* Configuration Status Table */}
      {configurations.length > 0 && (
        <Card>
          <CardContent>
            <h3>📋 Configuration Status</h3>
            {renderConfigurationTable()}
          </CardContent>
        </Card>
      )}

      {/* Test Result Dialog */}
      <Dialog open={testDialogOpen} onClose={() => setTestDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>
          {testResult?.status === 'success' ? '✓ Connection Successful' : '✗ Connection Failed'}
        </DialogTitle>
        <DialogContent>
          {testResult && (
            <Box sx={{ marginTop: 2 }}>
              <p><strong>Provider:</strong> {testResult.provider.toUpperCase()}</p>
              <p><strong>Message:</strong> {testResult.message}</p>
              {testResult.details && (
                <Box sx={{
                  backgroundColor: '#f5f5f5',
                  padding: 2,
                  borderRadius: 1,
                  marginTop: 2,
                  fontFamily: 'monospace',
                  fontSize: '0.9em'
                }}>
                  <pre>{JSON.stringify(testResult.details, null, 2)}</pre>
                </Box>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setTestDialogOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
