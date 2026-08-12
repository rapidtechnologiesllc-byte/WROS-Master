// DEFECT-8: Opportunity auto-defaults utility
// Auto-populate owner and client fields when creating opportunities

export function getDefaultOpportunityOwner() {
  // Try to get current user from auth context or localStorage
  // Can be integrated with useAuth hook if available
  // Returns current logged-in user's ID for auto-population
  try {
    // Placeholder: would use useAuth() or get from context
    // const { currentUser } = useAuth();
    // return currentUser?.id;
    return null; // Will be set by form component
  } catch (e) {
    return null;
  }
}

export function autoPopulateOpportunityFromJob(job) {
  // When job is selected, auto-populate:
  // - client_id from job.client_id
  // - client_owner_id from job.client_owner_id (DEFECT-4)
  // Returns object with auto-populated fields
  if (!job) return {};

  return {
    clientId: job.client_id || "",
    clientOwnerId: job.client_owner_id || "",
    // Revenue can be estimated from job's billing rate if available
    // revenueValue: job.billing_rate_usd_cents ? (job.billing_rate_usd_cents / 100) : ""
  };
}
