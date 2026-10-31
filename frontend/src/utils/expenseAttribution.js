// Who an expense is on, as one line for expense tables: "NAMIC 2026 -- Acme 60%, Globex 40%",
// "Acme", or "Internal" (CEO 2026-10-31: every expense says who it is on).
export const expenseOnWhom = (e) => {
  if (e.spend_for === "SPLIT") {
    return (e.client_shares || [])
      .map((s) => `${s.company_name || "Client"} ${(s.share_bps / 100).toFixed(0)}%`)
      .join(", ");
  }
  if (e.spend_for === "CLIENT" || e.client_id) return e.client_name || "Client";
  return "Internal";
};

export const expenseSubject = (e) => {
  const what = e.conference_name || e.investment_label;
  return what ? `${what} -- ${expenseOnWhom(e)}` : expenseOnWhom(e);
};
