// Mobile number as country code + digits, used by Add Candidate and the
// profile's Basic Information section so both store the same format:
// "+<code><digits>" (e.g. "+919876543210").
import Input from "./Input";
import Select from "./Select";

// The countries this platform recruits in/for; extend as needed.
export const COUNTRY_CODES = [
  { value: "+91", label: "+91 (India)" },
  { value: "+1", label: "+1 (US/Canada)" },
  { value: "+44", label: "+44 (UK)" },
  { value: "+61", label: "+61 (Australia)" },
  { value: "+971", label: "+971 (UAE)" },
  { value: "+65", label: "+65 (Singapore)" },
  { value: "+49", label: "+49 (Germany)" },
  { value: "+63", label: "+63 (Philippines)" },
];

export const DEFAULT_COUNTRY_CODE = "+91";

// "+919876543210" -> { code: "+91", number: "9876543210" }. Longest code
// first so "+1" never swallows "+12...". Unknown or missing prefix keeps
// the digits and the default code.
export function splitPhone(full) {
  const text = String(full || "").replace(/[\s()-]/g, "");
  if (!text) return { code: DEFAULT_COUNTRY_CODE, number: "" };
  const codes = COUNTRY_CODES.map((c) => c.value).sort((a, b) => b.length - a.length);
  const match = codes.find((c) => text.startsWith(c));
  if (match) return { code: match, number: text.slice(match.length) };
  return { code: DEFAULT_COUNTRY_CODE, number: text.replace(/\D/g, "") };
}

export function joinPhone(code, number) {
  const digits = String(number || "").replace(/\D/g, "");
  return digits ? `${code || DEFAULT_COUNTRY_CODE}${digits}` : "";
}

export default function PhoneField({ label = "Mobile", code, number, onCodeChange, onNumberChange, error, actionNotice, disabled }) {
  return (
    <div className="grid grid-cols-[minmax(0,7rem)_1fr] gap-2">
      <Select label="Code" value={code || DEFAULT_COUNTRY_CODE} onChange={onCodeChange} options={COUNTRY_CODES} disabled={disabled} />
      <Input
        label={label}
        value={number || ""}
        onChange={(value) => onNumberChange(String(value).replace(/\D/g, "").slice(0, 15))}
        type="tel"
        actionNotice={actionNotice}
        error={error}
        disabled={disabled}
      />
    </div>
  );
}
