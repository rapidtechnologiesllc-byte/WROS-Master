// Labeled select control.
// options: string[] or { value: string, label: string }[] (mixed allowed).
export default function Select({ label, value, onChange, options }) {
  return (
    <label className="block">
      <div className="mb-1 text-xs font-semibold text-gray-700">{label}</div>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-xl border bg-white px-3 py-2 text-sm outline-none focus:border-gray-900"
      >
        {options.map((o, idx) => {
          if (o == null) return null;
          const isObject =
            typeof o === "object" &&
            o !== null &&
            Object.prototype.hasOwnProperty.call(o, "value");
          const optValue = isObject ? String(o.value) : String(o);
          const optLabel =
            isObject && o.label != null ? String(o.label) : String(o);
          const key =
            optValue === "" ? `opt-empty-${idx}` : `${optValue}-${idx}`;
          return (
            <option key={key} value={optValue}>
              {optLabel}
            </option>
          );
        })}
      </select>
    </label>
  );
}
