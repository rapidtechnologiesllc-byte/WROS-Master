// The client bill rate as agreed: an amount in a currency per hour, month or year, in one field.
// Used wherever a bill rate is entered (add allocation, edit allocation). The server values it in
// USD per hour for the margin and the P&L; the invoice is in the client's currency.
export const BASIS_LABELS = { HOURLY: "per hour", MONTHLY: "per month", ANNUAL: "per year" };
export const DEFAULT_BASIS = "HOURLY";

export default function BillRateField({
  label, amount, onAmount, currency, onCurrency, basis, onBasis, currencies, bases, placeholder,
}) {
  const select = "border-l border-gray-300 bg-white px-1 py-2 text-sm text-gray-900 outline-none";
  return (
    <div className="block">
      <div className="mb-1 text-xs font-semibold text-gray-700">{label}</div>
      <div className="flex flex-wrap overflow-hidden rounded-xl border bg-white transition focus-within:border-gray-900">
        <input type="number" min="0" step="0.01" value={amount} placeholder={placeholder} aria-label="Bill rate amount"
          onChange={(e) => onAmount(e.target.value)}
          className="min-w-[6rem] flex-1 border-0 bg-white px-3 py-2 text-sm text-gray-900 outline-none placeholder:text-gray-400" />
        <select value={currency} onChange={(e) => onCurrency(e.target.value)} aria-label="Bill rate currency" className={select}>
          {currencies.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <select value={basis} onChange={(e) => onBasis(e.target.value)} aria-label="Bill rate period" className={select}>
          {bases.map((b) => <option key={b} value={b}>{BASIS_LABELS[b] || b}</option>)}
        </select>
      </div>
    </div>
  );
}
