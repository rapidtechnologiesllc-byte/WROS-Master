// EPIC-16 Finance & Accounting Operations -- one screen for the whole
// epic (Fully Loaded Cost, Blended Delivery Rate, BU P&L, Reserve
// Fund, Hiring Affordability, Intercompany Ledger), not one screen
// per engine. A single Business Unit + Year/Month selector at the top
// drives every read-only panel below -- pick once, see everything for
// that BU/period, matching the "fewer clicks, more outcome" mandate.
import { useEffect, useState } from "react";
import { Wallet, DollarSign, Building2, RefreshCw, Search, Receipt, CheckCircle2 } from "lucide-react";
import { Card, Button, Input, Select, Table } from "../components/ui";
import { listBusinessUnits } from "../services/api/rbac";
import { searchUsers } from "../services/api/users";
import {
  setCostRateConfig,
  getBuPnl,
  getBlendedDeliveryRate,
  recordReserveFundEntry,
  getReserveFundStatus,
  checkHiringAffordability,
  recordIntercompanySettlement,
  listIntercompanySettlements,
  getFullyLoadedCost,
  getEntityNetPosition,
} from "../services/api/financeOperations";
import {
  getPartnerIncentiveEvents,
  calculateRevenueShare,
  createIncentiveRule,
} from "../services/api/partnerIncentives";
import { listAllExpenses, approveExpense } from "../services/api/expenses";

const INCENTIVE_TYPES = [
  { label: "Revenue Share", value: "REVENUE_SHARE" },
  { label: "New Logo Bonus", value: "NEW_LOGO_BONUS" },
];

const formatUsdCents = (cents) =>
  cents == null
    ? "—"
    : `$${(cents / 100).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;

export default function FinanceOperationsScreen() {
  const now = new Date();
  const [businessUnits, setBusinessUnits] = useState([]);
  const [businessUnitId, setBusinessUnitId] = useState("");
  const [year, setYear] = useState(String(now.getFullYear()));
  const [month, setMonth] = useState(String(now.getMonth() + 1));

  const [pnl, setPnl] = useState(null);
  const [deliveryRate, setDeliveryRate] = useState(null);
  const [reserveFund, setReserveFund] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [statutoryPct, setStatutoryPct] = useState("");
  const [overheadPct, setOverheadPct] = useState("");

  const [reserveAmount, setReserveAmount] = useState("");
  const [reserveType, setReserveType] = useState("CONTRIBUTION");

  const [proposedSalary, setProposedSalary] = useState("");
  const [affordability, setAffordability] = useState(null);

  const [settlements, setSettlements] = useState([]);
  const [fromEntity, setFromEntity] = useState("BXUS");
  const [toEntity, setToEntity] = useState("BXIN");
  const [settlementAmount, setSettlementAmount] = useState("");
  const [settlementReason, setSettlementReason] = useState("");

  const [partners, setPartners] = useState([]);
  const [incentivePartnerId, setIncentivePartnerId] = useState("");
  const [incentiveEvents, setIncentiveEvents] = useState([]);

  const [ruleIncentiveType, setRuleIncentiveType] = useState("REVENUE_SHARE");
  const [ruleAmount, setRuleAmount] = useState("");
  const [ruleRevSharePct, setRuleRevSharePct] = useState("");
  const [ruleTriggerDescription, setRuleTriggerDescription] = useState("");
  const [ruleSaving, setRuleSaving] = useState(false);

  const [costLookupEmployeeId, setCostLookupEmployeeId] = useState("");
  const [costLookupResult, setCostLookupResult] = useState(null);
  const [costLookupError, setCostLookupError] = useState("");
  const [costLookupLoading, setCostLookupLoading] = useState(false);

  const [netPositionEntity, setNetPositionEntity] = useState("BXUS");
  const [netPositionResult, setNetPositionResult] = useState(null);
  const [netPositionError, setNetPositionError] = useState("");
  const [netPositionLoading, setNetPositionLoading] = useState(false);

  const [allExpenses, setAllExpenses] = useState([]);
  const [expensesLoading, setExpensesLoading] = useState(false);
  const [expensesError, setExpensesError] = useState("");
  const [approvingExpenseId, setApprovingExpenseId] = useState(null);

  const loadAllExpenses = async () => {
    setExpensesLoading(true);
    setExpensesError("");
    try {
      const res = await listAllExpenses();
      setAllExpenses(res?.expenses || []);
    } catch (err) {
      setExpensesError(err.message || "Failed to load expenses.");
    } finally {
      setExpensesLoading(false);
    }
  };

  useEffect(() => {
    listBusinessUnits()
      .then((list) => setBusinessUnits(list || []))
      .catch((err) => console.error("Failed to load business units:", err));
    listIntercompanySettlements()
      .then((list) => setSettlements(list || []))
      .catch((err) => console.error("Failed to load intercompany settlements:", err));
    searchUsers({ permission_role: "Partner", limit: 100 })
      .then((res) => setPartners(res?.users || []))
      .catch((err) => console.error("Failed to load partners:", err));
    loadAllExpenses();
  }, []);

  const partnerOptions = [
    { label: "Select Partner", value: "", disabled: true },
    ...partners.map((p) => ({ label: `${p.user_name} (${p.user_email})`, value: p.user_id })),
  ];

  useEffect(() => {
    if (!incentivePartnerId) {
      setIncentiveEvents([]);
      return;
    }
    getPartnerIncentiveEvents(incentivePartnerId)
      .then((res) => setIncentiveEvents(res?.events || []))
      .catch((err) => console.error("Failed to load incentive events:", err));
  }, [incentivePartnerId]);

  const handleCalculateRevenueShare = async () => {
    try {
      await calculateRevenueShare(incentivePartnerId, Number(year), Number(month));
      const res = await getPartnerIncentiveEvents(incentivePartnerId);
      setIncentiveEvents(res?.events || []);
    } catch (err) {
      setError(err.message || "Failed to calculate revenue share.");
    }
  };

  const handleCreateIncentiveRule = async () => {
    if (!incentivePartnerId) {
      setError("Select a Partner above before creating an incentive rule.");
      return;
    }
    setRuleSaving(true);
    setError("");
    try {
      await createIncentiveRule({
        partner_user_id: incentivePartnerId,
        incentive_type: ruleIncentiveType,
        amount_usd_cents:
          ruleIncentiveType === "NEW_LOGO_BONUS" && ruleAmount
            ? Math.round(parseFloat(ruleAmount) * 100)
            : null,
        revenue_share_pct:
          ruleIncentiveType === "REVENUE_SHARE" && ruleRevSharePct
            ? parseFloat(ruleRevSharePct)
            : null,
        trigger_description: ruleTriggerDescription || null,
      });
      setRuleAmount("");
      setRuleRevSharePct("");
      setRuleTriggerDescription("");
      const res = await getPartnerIncentiveEvents(incentivePartnerId);
      setIncentiveEvents(res?.events || []);
    } catch (err) {
      setError(err.message || "Failed to create incentive rule.");
    } finally {
      setRuleSaving(false);
    }
  };

  const handleLookupFullyLoadedCost = async () => {
    if (!costLookupEmployeeId.trim()) return;
    setCostLookupLoading(true);
    setCostLookupError("");
    setCostLookupResult(null);
    try {
      const res = await getFullyLoadedCost(costLookupEmployeeId.trim(), businessUnitId || undefined);
      setCostLookupResult(res);
    } catch (err) {
      setCostLookupError(err.message || "Failed to look up fully loaded cost.");
    } finally {
      setCostLookupLoading(false);
    }
  };

  const handleLookupNetPosition = async () => {
    if (!netPositionEntity.trim()) return;
    setNetPositionLoading(true);
    setNetPositionError("");
    setNetPositionResult(null);
    try {
      const res = await getEntityNetPosition(netPositionEntity.trim());
      setNetPositionResult(res);
    } catch (err) {
      setNetPositionError(err.message || "Failed to look up entity net position.");
    } finally {
      setNetPositionLoading(false);
    }
  };

  const handleApproveExpense = async (expenseId) => {
    setApprovingExpenseId(expenseId);
    setExpensesError("");
    try {
      await approveExpense(expenseId);
      await loadAllExpenses();
    } catch (err) {
      setExpensesError(err.message || "Failed to approve expense.");
    } finally {
      setApprovingExpenseId(null);
    }
  };

  const buOptions = [
    { label: "Select Business Unit", value: "", disabled: true },
    ...businessUnits.map((bu) => ({ label: bu.name, value: bu.id })),
  ];

  const load = async () => {
    if (!businessUnitId) return;
    setLoading(true);
    setError("");
    try {
      const [pnlRes, rateRes, reserveRes] = await Promise.all([
        getBuPnl(businessUnitId, Number(year), Number(month)),
        getBlendedDeliveryRate(businessUnitId, Number(year), Number(month)),
        getReserveFundStatus(businessUnitId, Number(year), Number(month)),
      ]);
      setPnl(pnlRes);
      setDeliveryRate(rateRes);
      setReserveFund(reserveRes);
    } catch (err) {
      setError(err.message || "Failed to load finance data for this BU/period.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [businessUnitId, year, month]);

  const handleSetCostRateConfig = async () => {
    try {
      await setCostRateConfig({
        business_unit_id: businessUnitId ? Number(businessUnitId) : null,
        statutory_pct: parseFloat(statutoryPct || "0"),
        overhead_pct: parseFloat(overheadPct || "0"),
      });
      setStatutoryPct("");
      setOverheadPct("");
      load();
    } catch (err) {
      setError(err.message || "Failed to set cost-rate config.");
    }
  };

  const handleRecordReserve = async () => {
    try {
      await recordReserveFundEntry({
        entry_type: reserveType,
        amount_usd_cents: Math.round(parseFloat(reserveAmount || "0") * 100),
        period_year: Number(year), period_month: Number(month),
        business_unit_id: Number(businessUnitId),
      });
      setReserveAmount("");
      load();
    } catch (err) {
      setError(err.message || "Failed to record reserve fund entry.");
    }
  };

  const handleCheckAffordability = async () => {
    try {
      const res = await checkHiringAffordability(
        businessUnitId, Math.round(parseFloat(proposedSalary || "0") * 100), Number(year), Number(month),
      );
      setAffordability(res);
    } catch (err) {
      setError(err.message || "Failed to check hiring affordability.");
    }
  };

  const handleRecordSettlement = async () => {
    try {
      await recordIntercompanySettlement({
        from_entity: fromEntity, to_entity: toEntity,
        amount_usd_cents: Math.round(parseFloat(settlementAmount || "0") * 100),
        settlement_date: new Date().toISOString().slice(0, 10),
        reason: settlementReason,
      });
      setSettlementAmount("");
      setSettlementReason("");
      const list = await listIntercompanySettlements();
      setSettlements(list || []);
    } catch (err) {
      setError(err.message || "Failed to record intercompany settlement.");
    }
  };

  return (
    <div className="space-y-4 p-6">
      <Card
        title="Finance Operations"
        subtitle="BU P&L, Reserve Fund, Hiring Affordability, Intercompany Ledger -- pick a Business Unit and period once, everything below reads for that scope."
        icon={<DollarSign className="h-4 w-4" />}
        right={
          <Button variant="ghost" onClick={load} disabled={loading || !businessUnitId}>
            <RefreshCw className={loading ? "h-4 w-4 animate-spin" : "h-4 w-4"} /> Refresh
          </Button>
        }
      >
        {error ? <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">{error}</div> : null}

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <Select label="Business Unit" value={businessUnitId} onChange={setBusinessUnitId} options={buOptions} />
          <Input label="Year" value={year} onChange={setYear} />
          <Input label="Month" value={month} onChange={setMonth} />
        </div>

        {!businessUnitId ? (
          <div className="mt-6 py-6 text-center text-sm text-gray-500">Select a Business Unit to see its finance picture.</div>
        ) : (
          <>
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <div className="rounded-xl border bg-white p-3">
                <div className="text-xs text-gray-500">Revenue</div>
                <div className="text-lg font-semibold text-gray-900">{formatUsdCents(pnl?.revenue_usd_cents)}</div>
              </div>
              <div className="rounded-xl border bg-white p-3">
                <div className="text-xs text-gray-500">Fully Loaded Cost</div>
                <div className="text-lg font-semibold text-gray-900">{formatUsdCents(pnl?.cost_usd_cents)}</div>
              </div>
              <div className="rounded-xl border bg-white p-3">
                <div className="text-xs text-gray-500">Gross Margin</div>
                <div className={`text-lg font-semibold ${pnl?.gross_margin_usd_cents < 0 ? "text-rose-700" : "text-emerald-700"}`}>
                  {formatUsdCents(pnl?.gross_margin_usd_cents)} {pnl?.margin_pct != null ? `(${pnl.margin_pct}%)` : ""}
                </div>
              </div>
            </div>
            {pnl && !pnl.cost_data_complete ? (
              <div className="mt-2 text-xs text-amber-700">Cost not fully computed -- set a Cost & Rate config below.</div>
            ) : null}

            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <div className="rounded-xl border bg-white p-3 text-sm">
                <div className="mb-1 text-xs text-gray-500">Blended Delivery Rate</div>
                <div className="font-semibold text-gray-900">
                  {deliveryRate?.blended_delivery_rate_usd_cents_per_hour != null
                    ? `${formatUsdCents(deliveryRate.blended_delivery_rate_usd_cents_per_hour)}/hr`
                    : "— (no approved billable hours yet)"}
                </div>
              </div>
              <div className="rounded-xl border bg-white p-3 text-sm">
                <div className="mb-1 text-xs text-gray-500">Reserve Fund</div>
                <div className="font-semibold text-gray-900">
                  {formatUsdCents(reserveFund?.balance_usd_cents)}
                  {reserveFund?.target_usd_cents != null
                    ? ` of ${formatUsdCents(reserveFund.target_usd_cents)} target (${reserveFund.pct_funded}%)`
                    : ""}
                </div>
              </div>
            </div>

            <div className="mt-6 grid gap-4 lg:grid-cols-2">
              <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4">
                <div className="mb-3 text-sm font-semibold text-gray-900">Set Cost & Rate Config</div>
                <div className="grid grid-cols-2 gap-3">
                  <Input label="Statutory %" value={statutoryPct} onChange={setStatutoryPct} placeholder="12" />
                  <Input label="Overhead %" value={overheadPct} onChange={setOverheadPct} placeholder="8" />
                </div>
                <Button className="mt-3" onClick={handleSetCostRateConfig}>Save</Button>
              </div>

              <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4">
                <div className="mb-3 text-sm font-semibold text-gray-900">
                  <Search className="mr-1 inline h-4 w-4" /> Fully Loaded Cost Lookup
                </div>
                <div className="flex gap-2">
                  <Input
                    label="Employee ID"
                    value={costLookupEmployeeId}
                    onChange={setCostLookupEmployeeId}
                    placeholder="EMP-1042"
                  />
                  <Button className="mt-5" onClick={handleLookupFullyLoadedCost} disabled={costLookupLoading || !costLookupEmployeeId.trim()}>
                    {costLookupLoading ? "Looking up…" : "Look Up"}
                  </Button>
                </div>
                <div className="mt-1 text-xs text-gray-500">Uses this Business Unit's active Cost & Rate config.</div>
                {costLookupError ? <div className="mt-2 text-xs text-rose-700">{costLookupError}</div> : null}
                {costLookupResult ? (
                  <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <div className="text-xs text-gray-500">Base Salary</div>
                      <div className="font-semibold text-gray-900">{formatUsdCents(costLookupResult.base_salary_usd_cents)}</div>
                    </div>
                    <div>
                      <div className="text-xs text-gray-500">Fully Loaded Cost</div>
                      <div className="font-semibold text-gray-900">{formatUsdCents(costLookupResult.fully_loaded_cost_usd_cents)}</div>
                    </div>
                  </div>
                ) : null}
              </div>

              <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4">
                <div className="mb-3 text-sm font-semibold text-gray-900">Reserve Fund Entry</div>
                <div className="grid grid-cols-2 gap-3">
                  <Select label="Type" value={reserveType} onChange={setReserveType} options={["CONTRIBUTION", "WITHDRAWAL"]} />
                  <Input label="Amount (USD)" value={reserveAmount} onChange={setReserveAmount} placeholder="5000" />
                </div>
                <Button className="mt-3" onClick={handleRecordReserve}>Record</Button>
              </div>

              <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4">
                <div className="mb-3 text-sm font-semibold text-gray-900">Hiring Affordability Check</div>
                <Input label="Proposed Annual Salary (USD)" value={proposedSalary} onChange={setProposedSalary} placeholder="90000" />
                <Button className="mt-3" onClick={handleCheckAffordability}>Check</Button>
                {affordability ? (
                  <div className={`mt-3 text-xs ${affordability.affordable ? "text-emerald-700" : "text-rose-700"}`}>
                    {affordability.affordable === null
                      ? affordability.reason
                      : affordability.affordable
                      ? `Affordable -- projected margin ${affordability.projected_margin_pct}%`
                      : affordability.reason}
                  </div>
                ) : null}
              </div>

              <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4">
                <div className="mb-3 text-sm font-semibold text-gray-900">
                  <Building2 className="mr-1 inline h-4 w-4" /> Intercompany Settlement
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <Input label="From Entity" value={fromEntity} onChange={setFromEntity} placeholder="BXUS" />
                  <Input label="To Entity" value={toEntity} onChange={setToEntity} placeholder="BXIN" />
                  <Input label="Amount (USD)" value={settlementAmount} onChange={setSettlementAmount} placeholder="5000" />
                  <Input label="Reason" value={settlementReason} onChange={setSettlementReason} placeholder="Offshore delivery reimbursement" />
                </div>
                <Button className="mt-3" onClick={handleRecordSettlement}>Record</Button>
                {settlements.length > 0 ? (
                  <div className="mt-3 space-y-1 text-xs text-gray-600">
                    {settlements.slice(0, 5).map((s) => (
                      <div key={s.id}>
                        {s.settlement_date}: {s.from_entity} → {s.to_entity} {formatUsdCents(s.amount_usd_cents)} ({s.reason})
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>

              <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4">
                <div className="mb-3 text-sm font-semibold text-gray-900">
                  <Building2 className="mr-1 inline h-4 w-4" /> Intercompany Net Position
                </div>
                <div className="flex gap-2">
                  <Input label="Entity" value={netPositionEntity} onChange={setNetPositionEntity} placeholder="BXUS" />
                  <Button className="mt-5" onClick={handleLookupNetPosition} disabled={netPositionLoading || !netPositionEntity.trim()}>
                    {netPositionLoading ? "Looking up…" : "Look Up"}
                  </Button>
                </div>
                {netPositionError ? <div className="mt-2 text-xs text-rose-700">{netPositionError}</div> : null}
                {netPositionResult ? (
                  <div className="mt-3 text-sm">
                    <div className="text-xs text-gray-500">Net Position for {netPositionResult.entity}</div>
                    <div
                      className={`text-lg font-semibold ${
                        netPositionResult.net_position_usd_cents < 0 ? "text-rose-700" : "text-emerald-700"
                      }`}
                    >
                      {formatUsdCents(netPositionResult.net_position_usd_cents)}
                    </div>
                  </div>
                ) : null}
              </div>

              <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4 lg:col-span-2">
                <div className="mb-3 text-sm font-semibold text-gray-900">
                  <Wallet className="mr-1 inline h-4 w-4" /> Partner Incentives
                </div>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                  <Select label="Partner" value={incentivePartnerId} onChange={setIncentivePartnerId} options={partnerOptions} />
                  <Button className="mt-5" onClick={handleCalculateRevenueShare} disabled={!incentivePartnerId}>
                    Calculate Revenue Share for {year}-{month}
                  </Button>
                </div>
                {incentiveEvents.length > 0 ? (
                  <div className="mt-3 space-y-1 text-xs text-gray-600">
                    {incentiveEvents.map((e) => (
                      <div key={e.id}>
                        {e.period_year ? `${e.period_year}-${e.period_month}` : "New Logo"}: {formatUsdCents(e.amount_usd_cents)} ({e.status})
                      </div>
                    ))}
                  </div>
                ) : incentivePartnerId ? (
                  <div className="mt-3 text-xs text-gray-500">No incentive events yet for this Partner.</div>
                ) : null}

                <div className="mt-4 border-t border-gray-200 pt-4">
                  <div className="mb-2 text-xs font-semibold text-gray-700">Create Incentive Rule for Selected Partner</div>
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <Select label="Type" value={ruleIncentiveType} onChange={setRuleIncentiveType} options={INCENTIVE_TYPES} />
                    {ruleIncentiveType === "REVENUE_SHARE" ? (
                      <Input label="Revenue Share %" value={ruleRevSharePct} onChange={setRuleRevSharePct} placeholder="5" />
                    ) : (
                      <Input label="Bonus Amount (USD)" value={ruleAmount} onChange={setRuleAmount} placeholder="2500" />
                    )}
                    <Input
                      label="Trigger Description"
                      value={ruleTriggerDescription}
                      onChange={setRuleTriggerDescription}
                      placeholder="Optional notes"
                    />
                    <Button
                      className="mt-5"
                      onClick={handleCreateIncentiveRule}
                      disabled={ruleSaving || !incentivePartnerId}
                    >
                      {ruleSaving ? "Saving…" : "Create Rule"}
                    </Button>
                  </div>
                  {!incentivePartnerId ? (
                    <div className="mt-2 text-xs text-gray-500">Select a Partner above first.</div>
                  ) : null}
                </div>
              </div>
            </div>
          </>
        )}
      </Card>

      <Card
        title="Expense Review"
        subtitle="All logged expenses across Clients/BUs -- approve pending spend. Not scoped to the Business Unit selected above."
        icon={<Receipt className="h-4 w-4" />}
        right={
          <Button variant="ghost" onClick={loadAllExpenses} disabled={expensesLoading}>
            <RefreshCw className={expensesLoading ? "h-4 w-4 animate-spin" : "h-4 w-4"} /> Refresh
          </Button>
        }
      >
        {expensesError ? (
          <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">{expensesError}</div>
        ) : null}
        {expensesLoading ? (
          <div className="py-8 text-center text-sm text-gray-500">Loading…</div>
        ) : allExpenses.length === 0 ? (
          <div className="py-8 text-center text-sm text-gray-500">No expenses logged yet.</div>
        ) : (
          <Table
            columns={[
              { key: "date", header: "Date" },
              { key: "purpose", header: "Purpose" },
              { key: "subject", header: "Subject" },
              { key: "category", header: "Category" },
              { key: "amount", header: "Amount" },
              { key: "status", header: "Status" },
              { key: "actions", header: "" },
            ]}
            rows={allExpenses.map((e) => ({
              date: e.expense_date,
              purpose: e.purpose.replace("_", " "),
              subject: e.conference_name || e.investment_label || (e.client_id ? "Client" : "—"),
              category: `${e.expense_category}${e.travel_type ? ` / ${e.travel_type}` : ""}`,
              amount: formatUsdCents(e.amount_usd_cents),
              status: (
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                    e.payment_status === "PENDING"
                      ? "bg-amber-50 text-amber-800"
                      : e.payment_status === "APPROVED"
                      ? "bg-blue-50 text-blue-800"
                      : "bg-emerald-50 text-emerald-800"
                  }`}
                >
                  {e.payment_status}
                </span>
              ),
              actions:
                e.payment_status === "PENDING" ? (
                  <Button
                    variant="success"
                    disabled={approvingExpenseId === e.id}
                    onClick={() => handleApproveExpense(e.id)}
                  >
                    <CheckCircle2 className="h-4 w-4" /> Approve
                  </Button>
                ) : null,
            }))}
          />
        )}
      </Card>
    </div>
  );
}
