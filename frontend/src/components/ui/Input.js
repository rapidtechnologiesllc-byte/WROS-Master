// Labeled input control.
export default function Input({
  label,
  value,
  onChange,
  placeholder,
  type = "text",
  disabled = false,
  readOnly = false,
  actionNotice,
  onFocus,
  onBlur,
}) {
  const handleChange = (e) => {
    if (!onChange || typeof onChange !== "function") return;
    const val = (e && e.target && e.target.value) || "";
    onChange(val);
  };

  return (
    <label className="block">
      <div className="mb-1 text-xs font-semibold text-gray-700">{label}</div>
      <input
        type={type}
        value={value ?? ""}
        placeholder={placeholder}
        onChange={disabled ? undefined : handleChange}
        onFocus={onFocus}
        onBlur={onBlur}
        disabled={disabled}
        readOnly={readOnly}
        style={{ border: '1.5px solid #4b5563' }}
        className={`w-full rounded-lg bg-white dark:bg-gray-800 px-4 py-3 text-base font-semibold font-sans text-gray-900 dark:text-gray-100 placeholder:text-gray-500 dark:placeholder:text-gray-400 outline-none transition-all duration-200 shadow-sm ${disabled ? 'bg-gray-100 dark:bg-gray-900 cursor-not-allowed opacity-60' : ''}`}
      />
    </label>
  );
}
