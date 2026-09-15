/**
 * API Keys Management Service
 * ==========================
 *
 * Service for interacting with backend API keys endpoints.
 * Manages credentials for delivery providers (Azure, Twilio, SendGrid).
 */

import { apiRequest } from './index';

/**
 * Get all configured API key providers for current tenant
 * @returns {Promise} Response with active_provider and list of configurations
 */
export const getAPIKeyConfigurations = async () => {
  return apiRequest('/api/v1/api-keys', { method: 'GET' });
};

/**
 * Save API key credentials for one or more providers
 * @param {Object} credentials - Provider credentials to save
 * @param {Object} credentials.azure - Azure Graph credentials (optional)
 * @param {Object} credentials.twilio - Twilio credentials (optional)
 * @param {Object} credentials.sendgrid - SendGrid credentials (optional)
 * @param {string} activeProvider - Which provider to set as active
 * @returns {Promise} Response with save status
 */
export const saveAPIKeyCredentials = async (credentials, activeProvider) => {
  const payload = {
    ...credentials,
    active_provider: activeProvider,
  };

  return apiRequest('/api/v1/api-keys', {
    method: 'POST',
    body: payload,
  });
};

/**
 * Test connection to a specific provider
 * @param {string} provider - Provider name ('azure', 'twilio', 'sendgrid', 'stub')
 * @returns {Promise} Test result with success/failure status
 */
export const testProviderConnection = async (provider) => {
  return apiRequest('/api/v1/api-keys/test', {
    method: 'POST',
    body: { provider },
  });
};

/**
 * Get health status of the currently active provider
 * @returns {Promise} Health status response
 */
export const getProviderStatus = async () => {
  return apiRequest('/api/v1/api-keys/status', { method: 'GET' });
};

/**
 * Validate Azure Graph credentials format
 * @param {Object} creds - Azure credentials
 * @returns {Array} Array of error messages (empty if valid)
 */
export const validateAzureCredentials = (creds) => {
  const errors = [];
  if (!creds.tenant_id?.trim()) errors.push('Tenant ID is required');
  if (!creds.client_id?.trim()) errors.push('Client ID is required');
  if (!creds.client_secret?.trim()) errors.push('Client Secret is required');
  return errors;
};

/**
 * Validate Twilio credentials format
 * @param {Object} creds - Twilio credentials
 * @returns {Array} Array of error messages (empty if valid)
 */
export const validateTwilioCredentials = (creds) => {
  const errors = [];
  if (!creds.account_sid?.trim()) errors.push('Account SID is required');
  if (!creds.auth_token?.trim()) errors.push('Auth Token is required');
  if (!creds.whatsapp_number?.trim()) errors.push('WhatsApp Number is required');
  // Basic phone number format validation
  if (creds.whatsapp_number && !creds.whatsapp_number.match(/^\+?[1-9]\d{1,14}$/)) {
    errors.push('WhatsApp Number must be in E.164 format (e.g., +1234567890)');
  }
  return errors;
};

/**
 * Validate SendGrid credentials format
 * @param {Object} creds - SendGrid credentials
 * @returns {Array} Array of error messages (empty if valid)
 */
export const validateSendGridCredentials = (creds) => {
  const errors = [];
  if (!creds.api_key?.trim()) errors.push('API Key is required');
  if (!creds.from_email?.trim()) errors.push('From Email is required');
  // Basic email validation
  if (creds.from_email && !creds.from_email.match(/^[^\s@]+@[^\s@]+\.[^\s@]+$/)) {
    errors.push('From Email must be a valid email address');
  }
  return errors;
};

/**
 * Mask a credential value for display (show only last 4 characters)
 * @param {string} value - The value to mask
 * @param {number} visibleChars - Number of characters to show at end (default 4)
 * @returns {string} Masked value
 */
export const maskCredential = (value, visibleChars = 4) => {
  if (!value || value.length <= visibleChars) return '****';
  return '*'.repeat(value.length - visibleChars) + value.slice(-visibleChars);
};

export default {
  getAPIKeyConfigurations,
  saveAPIKeyCredentials,
  testProviderConnection,
  getProviderStatus,
  validateAzureCredentials,
  validateTwilioCredentials,
  validateSendGridCredentials,
  maskCredential,
};
