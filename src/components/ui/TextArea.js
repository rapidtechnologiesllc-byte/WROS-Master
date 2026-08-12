// Labeled textarea control.
export default function TextArea({
  label,
  value,
  onChange,
  placeholder,
  rows = 3,
  disabled = false
}) {
  return (
    <label className="block">
      <div className="mb-1 text-xs font-semibold text-gray-700">{label}</div>
      <textarea
        rows={rows}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange?.(e.target.value)}
        disabled={disabled}
        className="w-full rounded-xl border bg-white px-3 py-2 text-sm outline-none ring-0 focus:border-gray-900 disabled:bg-gray-100"
      />
    </label>
  );
}
