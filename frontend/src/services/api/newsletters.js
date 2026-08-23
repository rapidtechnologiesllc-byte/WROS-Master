// Newsletter API wrappers.
import { apiRequest } from "./client";

// ========== Subscriber Endpoints ==========

export const subscribeNewsletter = async (payload) => {
  const { data } = await apiRequest("/newsletters/subscribe", {
    method: "POST",
    body: JSON.stringify({
      email: payload.email,
      name: payload.name || null,
      is_active: payload.is_active !== false
    })
  });
  return data;
};

export const unsubscribeNewsletter = async (email) => {
  const { data } = await apiRequest(`/newsletters/unsubscribe/${encodeURIComponent(email)}`, {
    method: "DELETE"
  });
  return data;
};

export const getSubscribers = async (skip = 0, limit = 100) => {
  const { data } = await apiRequest(`/newsletters/subscribers?skip=${skip}&limit=${limit}`, {
    method: "GET"
  });
  return data;
};

// ========== Newsletter Endpoints ==========

export const createNewsletter = async (payload) => {
  const { data } = await apiRequest("/newsletters/create", {
    method: "POST",
    body: JSON.stringify({
      subject: payload.subject,
      content: payload.content
    })
  });
  return data;
};

export const getNewsletters = async (skip = 0, limit = 100, status) => {
  const params = new URLSearchParams({ skip, limit });
  if (status) params.set("status", status);
  const { data } = await apiRequest(`/newsletters/all?${params.toString()}`, {
    method: "GET"
  });
  return data;
};

export const getDispatchedNewsletters = async (skip = 0, limit = 100) => {
  const { data } = await apiRequest(`/newsletters/dispatched?skip=${skip}&limit=${limit}`, {
    method: "GET"
  });
  return data;
};

export const updateNewsletter = async (newsletterId, payload) => {
  const body = {};
  if (payload.subject != null) body.subject = payload.subject;
  if (payload.content != null) body.content = payload.content;
  if (payload.status != null) body.status = payload.status;
  if (payload.scheduled_for != null) body.scheduled_for = payload.scheduled_for;

  const { data } = await apiRequest(`/newsletters/update/${newsletterId}`, {
    method: "PUT",
    body: JSON.stringify(body)
  });
  return data;
};

export const scheduleNewsletter = async (newsletterId, scheduledFor) => {
  const { data } = await apiRequest(`/newsletters/schedule/${newsletterId}`, {
    method: "POST",
    body: JSON.stringify({ scheduled_for: scheduledFor })
  });
  return data;
};

export const sendNewsletterNow = async (newsletterId) => {
  const { data } = await apiRequest(`/newsletters/send/${newsletterId}`, {
    method: "POST"
  });
  return data;
};

export const deleteNewsletter = async (newsletterId) => {
  await apiRequest(`/newsletters/delete/${newsletterId}`, {
    method: "DELETE"
  });
};
