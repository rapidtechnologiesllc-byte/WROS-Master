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
    const val = (e && e.target && e.target.value) || "";
    onChange(val);
  };

  const numRows = Number(rows);
  return (
    <label className="block">
      <div className="mb-1 text-xs font-semibold text-gray-700">{label}</div>
      <textarea
        rows={numRows === 1 ? undefined : numRows}
        value={value ?? ""}
        placeholder={placeholder}
        onChange={disabled ? undefined : handleChange}
        disabled={disabled}
        style={{
          border: '1.5px solid #4b5563',
          lineHeight: '1.3',
          padding: '6px 16px',
          fontSize: '14px',
          overflow: 'hidden',
          boxSizing: 'border-box',
          height: numRows === 1 ? '44px' : 'auto',
          minHeight: numRows === 1 ? '44px' : 'auto'
        }}
        className="w-full rounded-lg bg-white dark:bg-gray-800 font-semibold font-sans text-gray-900 dark:text-gray-100 placeholder:text-gray-500 dark:placeholder:text-gray-400 outline-none transition-all duration-200 shadow-sm focus:bg-white dark:focus:bg-gray-800 disabled:bg-gray-100 dark:disabled:bg-gray-900 disabled:cursor-not-allowed disabled:opacity-60 resize-none"
      />
    </label>
  );
}
