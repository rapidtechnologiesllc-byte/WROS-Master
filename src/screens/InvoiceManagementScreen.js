import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Plus, ChevronDown, Eye, CheckCircle2, Send, CreditCard, AlertCircle } from 'lucide-react';
import './InvoiceManagementScreen.css';

const InvoiceManagementScreen = () => {
  // State management
  const [invoices, setInvoices] = useState([]);
  const [filteredInvoices, setFilteredInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedInvoice, setSelectedInvoice] = useState(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showDetailPanel, setShowDetailPanel] = useState(false);

  // Filters
  const [filters, setFilters] = useState({
    status: 'ALL',
    searchText: '',
    dateFrom: '',
    dateTo: '',
    businessUnit: 'ALL',
  });

  // Form state for creating invoice
  const [createForm, setCreateForm] = useState({
    projectId: '',
    opportunityId: '',
    billingPeriodStart: '',
    billingPeriodEnd: '',
    currency: 'USD',
  });

  // Load invoices on mount
  useEffect(() => {
    fetchInvoices();
  }, []);

  // Apply filters
  useEffect(() => {
    let filtered = invoices;

    if (filters.status !== 'ALL') {
      filtered = filtered.filter(inv => inv.status === filters.status);
    }

    if (filters.searchText) {
      const search = filters.searchText.toLowerCase();
      filtered = filtered.filter(inv =>
        inv.id.toLowerCase().includes(search) ||
        inv.client_name?.toLowerCase().includes(search) ||
        inv.project_name?.toLowerCase().includes(search)
      );
    }

    if (filters.dateFrom) {
      filtered = filtered.filter(inv => new Date(inv.billing_period_end) >= new Date(filters.dateFrom));
    }

    if (filters.dateTo) {
      filtered = filtered.filter(inv => new Date(inv.billing_period_start) <= new Date(filters.dateTo));
    }

    if (filters.businessUnit !== 'ALL') {
      filtered = filtered.filter(inv => inv.business_unit_id === parseInt(filters.businessUnit));
    }

    setFilteredInvoices(filtered);
  }, [filters, invoices]);

  // Fetch invoices from API
  const fetchInvoices = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/v1/invoices', {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
      });

      if (!response.ok) throw new Error('Failed to fetch invoices');

      const data = await response.json();
      setInvoices(data.invoices || []);
      setError(null);
    } catch (err) {
      setError(err.message);
      console.error('Error fetching invoices:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Handle invoice creation
  const handleCreateInvoice = useCallback(async () => {
    if (!createForm.projectId || !createForm.billingPeriodStart || !createForm.billingPeriodEnd) {
      setError('Please fill in all required fields');
      return;
    }

    try {
      const response = await fetch('/api/v1/invoices', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          project_id: createForm.projectId,
          opportunity_id: createForm.opportunityId || null,
          billing_period_start: createForm.billingPeriodStart,
          billing_period_end: createForm.billingPeriodEnd,
          currency: createForm.currency,
        }),
      });

      if (!response.ok) throw new Error('Failed to create invoice');

      const newInvoice = await response.json();
      setInvoices([...invoices, newInvoice]);
      setShowCreateModal(false);
      setCreateForm({ projectId: '', opportunityId: '', billingPeriodStart: '', billingPeriodEnd: '', currency: 'USD' });
      setError(null);
    } catch (err) {
      setError(err.message);
    }
  }, [createForm, invoices]);

  // Handle status transitions
  const handleStatusTransition = useCallback(async (invoiceId, newStatus) => {
    try {
      let endpoint = '';
      if (newStatus === 'APPROVED') endpoint = `/api/v1/invoices/${invoiceId}/approve`;
      else if (newStatus === 'SENT') endpoint = `/api/v1/invoices/${invoiceId}/send`;
      else if (newStatus === 'PAID') endpoint = `/api/v1/invoices/${invoiceId}/mark-paid`;

      if (!endpoint) return;

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
      });

      if (!response.ok) throw new Error(`Failed to transition invoice`);

      const updated = await response.json();
      setInvoices(invoices.map(inv => inv.id === invoiceId ? updated : inv));

      if (selectedInvoice?.id === invoiceId) {
        setSelectedInvoice(updated);
      }

      setError(null);
    } catch (err) {
      setError(err.message);
    }
  }, [invoices, selectedInvoice]);

  // Handle view details
  const handleViewDetails = useCallback((invoice) => {
    setSelectedInvoice(invoice);
    setShowDetailPanel(true);
  }, []);

  // Status badge styling
  const getStatusBadge = (status) => {
    const styles = {
      DRAFT: 'badge-draft',
      APPROVED: 'badge-approved',
      SENT: 'badge-sent',
      PAID: 'badge-paid',
    };
    return styles[status] || '';
  };

  // Format currency
  const formatCurrency = (cents) => `$${(cents / 100).toFixed(2)}`;

  // Summary cards
  const summaryStats = useMemo(() => {
    const stats = {
      draft: { count: 0, total: 0 },
      approved: { count: 0, total: 0 },
      sent: { count: 0, total: 0 },
      paid: { count: 0, total: 0 },
    };

    invoices.forEach(inv => {
      const key = inv.status?.toLowerCase();
      if (stats[key]) {
        stats[key].count += 1;
        stats[key].total += inv.total_usd_cents || 0;
      }
    });

    return stats;
  }, [invoices]);

  if (loading) {
    return (
      <div className="invoice-management-screen">
        <div className="loading-state">Loading invoices...</div>
      </div>
    );
  }

  return (
    <div className="invoice-management-screen">
      {/* Header */}
      <div className="screen-header">
        <h1>Invoice Management</h1>
        <p className="text-muted">Track, approve, and mark invoices as paid • Revenue recognized when PAID</p>
        <button className="btn btn-primary" onClick={() => setShowCreateModal(true)}>
          <Plus size={18} />
          Create Invoice
        </button>
      </div>

      {/* Summary Cards */}
      <div className="summary-cards">
        <div className="summary-card draft">
          <div className="card-icon">📋</div>
          <div className="card-content">
            <div className="card-label">Draft</div>
            <div className="card-value">{summaryStats.draft.count}</div>
            <div className="card-amount">{formatCurrency(summaryStats.draft.total)}</div>
          </div>
        </div>

        <div className="summary-card approved">
          <div className="card-icon">✓</div>
          <div className="card-content">
            <div className="card-label">Approved</div>
            <div className="card-value">{summaryStats.approved.count}</div>
            <div className="card-amount">{formatCurrency(summaryStats.approved.total)}</div>
          </div>
        </div>

        <div className="summary-card sent">
          <div className="card-icon">📤</div>
          <div className="card-content">
            <div className="card-label">Sent to Client</div>
            <div className="card-value">{summaryStats.sent.count}</div>
            <div className="card-amount">{formatCurrency(summaryStats.sent.total)}</div>
          </div>
        </div>

        <div className="summary-card paid">
          <div className="card-icon">💰</div>
          <div className="card-content">
            <div className="card-label">Paid (Revenue)</div>
            <div className="card-value">{summaryStats.paid.count}</div>
            <div className="card-amount">{formatCurrency(summaryStats.paid.total)}</div>
          </div>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="alert alert-error">
          <AlertCircle size={18} />
          <span>{error}</span>
          <button onClick={() => setError(null)}>×</button>
        </div>
      )}

      {/* Filters */}
      <div className="filters-section">
        <div className="filter-group">
          <label>Status</label>
          <select value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value })}>
            <option value="ALL">All Statuses</option>
            <option value="DRAFT">Draft</option>
            <option value="APPROVED">Approved</option>
            <option value="SENT">Sent</option>
            <option value="PAID">Paid</option>
          </select>
        </div>

        <div className="filter-group">
          <label>Search</label>
          <input
            type="text"
            placeholder="Invoice ID, client, project..."
            value={filters.searchText}
            onChange={(e) => setFilters({ ...filters, searchText: e.target.value })}
          />
        </div>

        <div className="filter-group">
          <label>Date From</label>
          <input
            type="date"
            value={filters.dateFrom}
            onChange={(e) => setFilters({ ...filters, dateFrom: e.target.value })}
          />
        </div>

        <div className="filter-group">
          <label>Date To</label>
          <input
            type="date"
            value={filters.dateTo}
            onChange={(e) => setFilters({ ...filters, dateTo: e.target.value })}
          />
        </div>
      </div>

      {/* Invoice List */}
      <div className="invoice-list">
        <table className="invoice-table">
          <thead>
            <tr>
              <th>Invoice ID</th>
              <th>Project</th>
              <th>Client</th>
              <th>Billing Period</th>
              <th>Amount</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredInvoices.length === 0 ? (
              <tr>
                <td colSpan="7" className="empty-state">No invoices found</td>
              </tr>
            ) : (
              filteredInvoices.map(invoice => (
                <tr key={invoice.id} className="invoice-row">
                  <td className="invoice-id">{invoice.id}</td>
                  <td className="invoice-project">{invoice.project_name}</td>
                  <td className="invoice-client">{invoice.client_name}</td>
                  <td className="invoice-period">
                    {new Date(invoice.billing_period_start).toLocaleDateString()} -
                    {' '}{new Date(invoice.billing_period_end).toLocaleDateString()}
                  </td>
                  <td className="invoice-amount">{formatCurrency(invoice.total_usd_cents)}</td>
                  <td>
                    <span className={`badge ${getStatusBadge(invoice.status)}`}>
                      {invoice.status}
                    </span>
                  </td>
                  <td className="invoice-actions">
                    <button
                      className="btn btn-sm btn-ghost"
                      title="View Details"
                      onClick={() => handleViewDetails(invoice)}
                    >
                      <Eye size={16} />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Create Invoice Modal */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Create Invoice</h2>
              <button onClick={() => setShowCreateModal(false)}>×</button>
            </div>

            <div className="modal-body">
              <div className="form-group">
                <label>Project *</label>
                <input
                  type="text"
                  placeholder="Select project"
                  value={createForm.projectId}
                  onChange={(e) => setCreateForm({ ...createForm, projectId: e.target.value })}
                />
              </div>

              <div className="form-group">
                <label>Opportunity (Optional)</label>
                <input
                  type="text"
                  placeholder="Link to opportunity for P&L tracking"
                  value={createForm.opportunityId}
                  onChange={(e) => setCreateForm({ ...createForm, opportunityId: e.target.value })}
                />
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Billing Period Start *</label>
                  <input
                    type="date"
                    value={createForm.billingPeriodStart}
                    onChange={(e) => setCreateForm({ ...createForm, billingPeriodStart: e.target.value })}
                  />
                </div>

                <div className="form-group">
                  <label>Billing Period End *</label>
                  <input
                    type="date"
                    value={createForm.billingPeriodEnd}
                    onChange={(e) => setCreateForm({ ...createForm, billingPeriodEnd: e.target.value })}
                  />
                </div>
              </div>

              <div className="form-group">
                <label>Currency</label>
                <select value={createForm.currency} onChange={(e) => setCreateForm({ ...createForm, currency: e.target.value })}>
                  <option value="USD">USD</option>
                  <option value="INR">INR</option>
                  <option value="GBP">GBP</option>
                  <option value="EUR">EUR</option>
                </select>
              </div>
            </div>

            <div className="modal-footer">
              <button className="btn btn-secondary" onClick={() => setShowCreateModal(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={handleCreateInvoice}>Create Invoice</button>
            </div>
          </div>
        </div>
      )}

      {/* Detail Panel */}
      {showDetailPanel && selectedInvoice && (
        <div className="detail-panel">
          <div className="panel-header">
            <h2>Invoice Details</h2>
            <button onClick={() => setShowDetailPanel(false)}>×</button>
          </div>

          <div className="panel-content">
            <div className="detail-section">
              <h3>Invoice Information</h3>
              <div className="detail-grid">
                <div className="detail-item">
                  <span className="label">Invoice ID:</span>
                  <span className="value">{selectedInvoice.id}</span>
                </div>
                <div className="detail-item">
                  <span className="label">Status:</span>
                  <span className={`badge ${getStatusBadge(selectedInvoice.status)}`}>{selectedInvoice.status}</span>
                </div>
                <div className="detail-item">
                  <span className="label">Project:</span>
                  <span className="value">{selectedInvoice.project_name}</span>
                </div>
                <div className="detail-item">
                  <span className="label">Client:</span>
                  <span className="value">{selectedInvoice.client_name}</span>
                </div>
              </div>
            </div>

            <div className="detail-section">
              <h3>Billing Details</h3>
              <div className="detail-grid">
                <div className="detail-item">
                  <span className="label">Billing Period:</span>
                  <span className="value">
                    {new Date(selectedInvoice.billing_period_start).toLocaleDateString()} -
                    {' '}{new Date(selectedInvoice.billing_period_end).toLocaleDateString()}
                  </span>
                </div>
                <div className="detail-item">
                  <span className="label">Total Amount:</span>
                  <span className="value amount">{formatCurrency(selectedInvoice.total_usd_cents)}</span>
                </div>
                <div className="detail-item">
                  <span className="label">Currency:</span>
                  <span className="value">{selectedInvoice.currency}</span>
                </div>
              </div>
            </div>

            {selectedInvoice.status === 'PAID' && (
              <div className="detail-section revenue-recognized">
                <h3>Revenue Recognized</h3>
                <p className="text-success">Revenue was recognized when this invoice was marked PAID.</p>
                <div className="detail-grid">
                  <div className="detail-item">
                    <span className="label">Revenue Amount:</span>
                    <span className="value">{formatCurrency(selectedInvoice.total_usd_cents)}</span>
                  </div>
                  <div className="detail-item">
                    <span className="label">Attributed to:</span>
                    <span className="value">{selectedInvoice.client_owner_name || 'Unknown'}</span>
                  </div>
                </div>
              </div>
            )}

            <div className="detail-section">
              <h3>Actions</h3>
              <div className="action-buttons">
                {selectedInvoice.status === 'DRAFT' && (
                  <button className="btn btn-primary" onClick={() => handleStatusTransition(selectedInvoice.id, 'APPROVED')}>
                    <CheckCircle2 size={18} />
                    Approve Invoice
                  </button>
                )}
                {selectedInvoice.status === 'APPROVED' && (
                  <button className="btn btn-primary" onClick={() => handleStatusTransition(selectedInvoice.id, 'SENT')}>
                    <Send size={18} />
                    Send to Client
                  </button>
                )}
                {selectedInvoice.status === 'SENT' && (
                  <button className="btn btn-success" onClick={() => handleStatusTransition(selectedInvoice.id, 'PAID')}>
                    <CreditCard size={18} />
                    Mark as Paid
                  </button>
                )}
                {selectedInvoice.status === 'PAID' && (
                  <div className="text-success">✓ Invoice Paid - Revenue Recognized</div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default InvoiceManagementScreen;
