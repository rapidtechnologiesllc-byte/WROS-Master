// Labeled input control.
export default function Input({
  label,
  value,
  onChange,
  placeholder,
  type = "text",
  disabled = false,
  readOnly = false
}) {
  return (
    <label className="block">
      <div className="mb-1 text-xs font-semibold text-gray-700">{label}</div>
      <input
        type={type}
        value={value}
        placeholder={placeholder}
        onChange={disabled ? undefined : (e) => onChange(e.target.value)}
        disabled={disabled}
        readOnly={readOnly}
        className="w-full rounded-xl border bg-white px-3 py-2 text-sm outline-none ring-0 focus:border-gray-900"
      />
    </label>
  );
}
