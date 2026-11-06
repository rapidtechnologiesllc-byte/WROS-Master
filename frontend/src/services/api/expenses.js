// Partner/BU expense tracking API wrappers, 2026-08-05. Self-service --
// logged_by_user_id is always resolved server-side from the caller's
// own token, never sent from here.
import { apiFetch, apiRequest } from "./client";

export const createExpense = async (payload) => {
  const { data } = await apiRequest("/expenses", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return data;
};

export const listMyExpenses = async () => {
  const { data } = await apiRequest("/expenses/mine", { method: "GET" });
  return data;
};

export const listAllExpenses = async ({ clientId, purpose } = {}) => {
  const params = new URLSearchParams();
  if (clientId) params.set("client_id", clientId);
  if (purpose) params.set("purpose", purpose);
  const qs = params.toString();
  const { data } = await apiRequest(`/expenses${qs ? `?${qs}` : ""}`, {
    method: "GET",
  });
  return data;
};

export const approveExpense = async (expenseId) => {
  const { data } = await apiRequest(`/expenses/${expenseId}/approve`, {
    method: "POST",
  });
  return data;
};

// Manager step: once approved the expense counts as a cost in the P&L
export const managerApproveExpense = async (expenseId) => {
  const { data } = await apiRequest(`/expenses/${expenseId}/manager-approve`, { method: "POST" });
  return data;
};

export const managerRejectExpense = async (expenseId, reason) => {
  const { data } = await apiRequest(`/expenses/${expenseId}/manager-reject`, {
    method: "POST",
    body: JSON.stringify({ reason: reason || null }),
  });
  return data;
};

export const getExpense = async (expenseId) => {
  const { data } = await apiRequest(`/expenses/${expenseId}`, { method: "GET" });
  return data;
};

// Correct your own expense, until Finance approves it
export const updateExpense = async (expenseId, payload) => {
  const { data } = await apiRequest(`/expenses/${expenseId}`, { method: "PUT", body: JSON.stringify(payload) });
  return data;
};

export const removeExpenseReceipt = async (expenseId, receiptId) => {
  const { data } = await apiRequest(`/expenses/${expenseId}/receipts/${receiptId}`, { method: "DELETE" });
  return data;
};

export const markExpensePaid = async (expenseId) => {
  const { data } = await apiRequest(`/expenses/${expenseId}/mark-paid`, { method: "POST" });
  return data;
};

// Who the spend is on (INTERNAL / CLIENT / SPLIT) and, for a conference, its shared event
export const updateExpenseAttribution = async (expenseId, payload) => {
  const { data } = await apiRequest(`/expenses/${expenseId}/attribution`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
  return data;
};

// The team's shared conferences, closest to `q` first ("Namic-2026" finds "NAMIC 2026")
export const searchExpenseEvents = async (q) => {
  const qs = q ? `?q=${encodeURIComponent(q)}` : "";
  const { data } = await apiRequest(`/expense-events${qs}`, { method: "GET" });
  return data;
};

// Pick-or-add: the same name and year returns the existing event; a near match throws a 409
// whose error.detail.matches lists the events it looks like (resend with confirm_new to add anyway)
export const createExpenseEvent = async (payload) => {
  const { data } = await apiRequest("/expense-events", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return data;
};

export const getExpenseEventSummary = async (eventId) => {
  const { data } = await apiRequest(`/expense-events/${eventId}/summary`, { method: "GET" });
  return data;
};

export const mergeExpenseEvent = async (eventId, intoEventId) => {
  const { data } = await apiRequest(`/expense-events/${eventId}/merge`, {
    method: "POST",
    body: JSON.stringify({ into_event_id: intoEventId }),
  });
  return data;
};

export const getClientInvestmentPosition = async (clientId) => {
  const { data } = await apiRequest(`/clients/${clientId}/investment-position`, {
    method: "GET",
  });
  return data;
};

// Attach a receipt (image or PDF); the server reads and checks it straight away and returns the
// updated expense (receipt_check_status MATCHED / MISMATCH / UNREADABLE)
export const uploadExpenseReceipt = async (expenseId, file) => {
  const body = new FormData();
  body.append("file", file);
  const { data } = await apiRequest(`/expenses/${expenseId}/receipt`, { method: "POST", body });
  return data;
};

// Photos are often larger than the web server accepts in one request, and a receipt reads fine smaller
const LARGEST_REQUEST_BYTES = 900 * 1024;
const LONGEST_PHOTO_SIDE = 2200;

const canvasToBlob = (canvas, quality) =>
  new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", quality));

const fitForUpload = async (file) => {
  if (file.size <= LARGEST_REQUEST_BYTES || !file.type.startsWith("image/")) return file;
  try {
    const bitmap = await createImageBitmap(file);
    let scale = Math.min(1, LONGEST_PHOTO_SIDE / Math.max(bitmap.width, bitmap.height));
    for (let attempt = 0; attempt < 6; attempt += 1) {
      const canvas = document.createElement("canvas");
      canvas.width = Math.round(bitmap.width * scale);
      canvas.height = Math.round(bitmap.height * scale);
      canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);
      const blob = await canvasToBlob(canvas, 0.8);
      if (blob && blob.size <= LARGEST_REQUEST_BYTES) {
        return new File([blob], file.name.replace(/\.[^.]+$/, "") + ".jpg", { type: "image/jpeg" });
      }
      scale *= 0.75;
    }
  } catch (err) {
    console.warn("[Expenses] Could not shrink the photo, sending it as it is:", err);
  }
  return file;
};

// Several receipts: one request per file (the web server limits each request), checked together after the last
export const uploadExpenseReceipts = async (expenseId, files, onProgress) => {
  let latest = null;
  for (let i = 0; i < files.length; i += 1) {
    const file = await fitForUpload(files[i]);
    if (onProgress) onProgress(i + 1, files.length);
    const body = new FormData();
    body.append("files", file);
    try {
      const { data } = await apiRequest(`/expenses/${expenseId}/receipts?check=${i === files.length - 1}`, { method: "POST", body });
      latest = data;
    } catch (err) {
      if (err?.status === 413 || /413|too large/i.test(err?.message || "")) {
        throw new Error(`${files[i].name} is too large for the server to accept. Save it as a smaller file and try again.`);
      }
      throw err;
    }
  }
  return latest;
};

// One receipt's file, for showing on screen
export const fetchExpenseReceiptBlob = async (expenseId, receiptId) => {
  const response = await apiFetch(`/expenses/${expenseId}/receipts/${receiptId}`);
  if (!response.ok) {
    throw new Error(`Receipt download failed (HTTP ${response.status})`);
  }
  return response.blob();
};

// Open a receipt in a new tab (authenticated download); the first one when none is named
export const openExpenseReceipt = async (expenseId, receiptId) => {
  const response = await apiFetch(receiptId ? `/expenses/${expenseId}/receipts/${receiptId}` : `/expenses/${expenseId}/receipt`);
  if (!response.ok) {
    throw new Error(`Receipt download failed (HTTP ${response.status})`);
  }
  const url = URL.createObjectURL(await response.blob());
  window.open(url, "_blank", "noopener");
  setTimeout(() => URL.revokeObjectURL(url), 60000);
};
