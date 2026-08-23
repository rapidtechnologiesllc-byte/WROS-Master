import React from "react";

export default function RateField({
  label,
  value,
  rateType,
  onValueChange,
  onRateTypeChange,
  required = false,
  disabled = false,
  rateTypeOptions = ["$/Hour", "$/Day", "$/Week", "$/Month", "$/Year"],
}) {
  return (
    <div>
      {label && (
        <label className="mb-1.5 block text-xs font-semibold text-gray-600">
          {label}
          {required && <span className="text-red-500 ml-1">*</span>}
        </label>
      )}
      <div className="flex overflow-hidden rounded-xl border border-gray-300 bg-white transition focus-within:border-gray-900">
        <input
          type="number"
          min="0"
          step="0.01"
          value={value ?? ""}
          disabled={disabled}
          onChange={(e) => onValueChange?.(e.target.value)}
          placeholder="Amount"
          className="min-w-0 flex-1 border-0 bg-white px-3 py-2 text-sm text-gray-900 outline-none placeholder:text-gray-400 disabled:cursor-not-allowed disabled:bg-gray-100 disabled:text-gray-500"
        />
        <select
          value={rateType || "$/Hour"}
          disabled={disabled}
          onChange={(e) => onRateTypeChange?.(e.target.value)}
          className="w-28 border-l border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 outline-none disabled:cursor-not-allowed disabled:bg-gray-100 disabled:text-gray-500"
        >
          {rateTypeOptions.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
