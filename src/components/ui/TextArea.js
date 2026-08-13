// Labeled textarea control.
export default function TextArea({
  label,
  value,
  onChange,
  placeholder,
  rows = 3,
  disabled = false
}) {
  const handleChange = (e) => {
    if (!onChange || typeof onChange !== "function") return;
    if (e && e.target && typeof e.target.value !== "undefined") {
      onChange(e.target.value);
    }
  };

  return (
    <label className="block">
      <div className="mb-1 text-xs font-semibold text-gray-700">{label}</div>
      <textarea
        rows={rows}
        value={value ?? ""}
        placeholder={placeholder}
        onChange={disabled ? undefined : handleChange}
        disabled={disabled}
        className="w-full rounded-xl border bg-white px-3 py-2 text-sm outline-none ring-0 focus:border-gray-900 disabled:bg-gray-100"
      />
    </label>
  );
}
