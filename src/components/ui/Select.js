// options: string[] or { value: string, label: string }[] (mixed allowed).
import { ChevronDown } from "lucide-react";

export default function Select({ label, value, onChange, options, disabled }) {
  return (
    <label className="block">
      {label ? (
        <div className="mb-1 text-xs font-semibold text-gray-700">{label}</div>
      ) : null}
      <div className="relative">
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          className="w-full appearance-none rounded-xl border bg-white px-3 py-2 pr-9 text-sm outline-none transition focus:border-gray-900 disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-400"
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
        <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
      </div>
    </label>
  );
}
