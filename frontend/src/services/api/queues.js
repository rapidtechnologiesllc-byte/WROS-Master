import { apiRequest } from './client';

export const getQueueStats = () =>
  (async () => {
    try {
      const response = await apiRequest('/queues/stats', { method: 'GET' });
      return response.data;
    } catch (err) {
      console.error('[getQueueStats]', err);
      throw err;
    }
  })();

export const getQueueMessages = (queueType, status, limit = 50, offset = 0) =>
  (async () => {
    try {
      const params = new URLSearchParams();
      if (queueType) params.append('queue_type', queueType);
      if (status) params.append('status', status);
      params.append('limit', limit);
      params.append('offset', offset);
      const response = await apiRequest(`/queues?${params.toString()}`, { method: 'GET' });
      return response.data;
    } catch (err) {
      console.error('[getQueueMessages]', err);
      throw err;
    }
  })();

export const getMessageDetail = (messageId) =>
  (async () => {
    try {
      const response = await apiRequest(`/queues/${messageId}`, { method: 'GET' });
      return response.data;
    } catch (err) {
      console.error('[getMessageDetail]', err);
      throw err;
    }
  })();

export const retryMessage = (messageId) =>
  (async () => {
    try {
      const response = await apiRequest(`/queues/${messageId}/retry`, { method: 'POST' });
      return response.data;
    } catch (err) {
      console.error('[retryMessage]', err);
      throw err;
    }
  })();

export const clearMessage = (messageId) =>
  (async () => {
    try {
      const response = await apiRequest(`/queues/${messageId}/clear`, { method: 'POST' });
      return response.data;
    } catch (err) {
      console.error('[clearMessage]', err);
      throw err;
    }
  })();

export const startQueue = (queueType) =>
  (async () => {
    try {
      const response = await apiRequest(`/queues/${queueType}/start`, { method: 'POST' });
      return response.data;
    } catch (err) {
      console.error('[startQueue]', err);
      throw err;
    }
  })();

export const stopQueue = (queueType) =>
  (async () => {
    try {
      const response = await apiRequest(`/queues/${queueType}/stop`, { method: 'POST' });
      return response.data;
    } catch (err) {
      console.error('[stopQueue]', err);
      throw err;
    }
  })();

export const retryQueue = (queueType) =>
  (async () => {
    try {
      const response = await apiRequest(`/queues/${queueType}/retry`, { method: 'POST' });
      return response.data;
    } catch (err) {
      console.error('[retryQueue]', err);
      throw err;
    }
  })();

export const getEmailEngagementMetrics = (messageId) =>
  (async () => {
    try {
      const response = await apiRequest(`/queues/email/${messageId}/engagement`, { method: 'GET' });
      return response.data;
    } catch (err) {
      console.error('[getEmailEngagementMetrics]', err);
      throw err;
    }
  })();
