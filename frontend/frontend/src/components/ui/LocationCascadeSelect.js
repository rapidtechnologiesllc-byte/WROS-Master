// Country -> State -> City cascading select, backed by the offline
// `country-state-city` dataset (250 countries, no network calls).
// Added 2026-07-23: Avinash's instruction to turn Current Location and
// Permanent Address from free text into structured, cascading dropdowns
// rather than typed text a candidate could enter inconsistently.
import { useMemo } from "react";
import { Country, State, City } from "country-state-city";

// value: { countryCode, stateCode, city } -- city is a plain name (city-level
// ISO codes don't exist in this dataset the way country/state ones do).
// onChange receives the next value object.
export default function LocationCascadeSelect({ value, onChange, disabled }) {
  const countryCode = value?.countryCode || "";
  const stateCode = value?.stateCode || "";
  const city = value?.city || "";

  const countries = useMemo(() => Country.getAllCountries(), []);
  const states = useMemo(
    () => (countryCode ? State.getStatesOfCountry(countryCode) : []),
    [countryCode],
  );
  const cities = useMemo(
    () =>
      countryCode && stateCode
        ? City.getCitiesOfState(countryCode, stateCode)
        : [],
    [countryCode, stateCode],
  );

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      <label className="block">
        <div className="mb-1 text-xs font-semibold text-gray-700">
          Country
        </div>
        <select
          value={countryCode}
          disabled={disabled}
          onChange={(e) =>
            onChange({ countryCode: e.target.value, stateCode: "", city: "" })
          }
          className="w-full rounded-xl border bg-white px-3 py-2 text-sm outline-none focus:border-gray-900"
        >
          <option value="">Select country</option>
          {countries.map((c) => (
            <option key={c.isoCode} value={c.isoCode}>
              {c.name}
            </option>
          ))}
        </select>
      </label>

      <label className="block">
        <div className="mb-1 text-xs font-semibold text-gray-700">State</div>
        <select
          value={stateCode}
          disabled={disabled || !countryCode}
          onChange={(e) =>
            onChange({ countryCode, stateCode: e.target.value, city: "" })
          }
          className="w-full rounded-xl border bg-white px-3 py-2 text-sm outline-none focus:border-gray-900 disabled:bg-gray-50 disabled:text-gray-400"
        >
          <option value="">
            {countryCode ? "Select state" : "Select country first"}
          </option>
          {states.map((s) => (
            <option key={s.isoCode} value={s.isoCode}>
              {s.name}
            </option>
          ))}
        </select>
      </label>

      <label className="block">
        <div className="mb-1 text-xs font-semibold text-gray-700">City</div>
        <select
          value={city}
          disabled={disabled || !stateCode}
          onChange={(e) => onChange({ countryCode, stateCode, city: e.target.value })}
          className="w-full rounded-xl border bg-white px-3 py-2 text-sm outline-none focus:border-gray-900 disabled:bg-gray-50 disabled:text-gray-400"
        >
          <option value="">
            {stateCode ? "Select city" : "Select state first"}
          </option>
          {cities.map((c) => (
            <option key={`${c.name}-${c.latitude}`} value={c.name}>
              {c.name}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}

// Composes a value object into the single "City, State, Country" string
// the backend's candidateCurrentLocation / permanent_address columns
// (both plain strings) already expect -- no backend schema change needed,
// this only changes how the string gets built on the frontend.
export function formatLocation(value) {
  if (!value?.countryCode) return "";
  const country = Country.getCountryByCode(value.countryCode);
  const state = value.stateCode
    ? State.getStateByCodeAndCountry(value.stateCode, value.countryCode)
    : null;
  return [value.city, state?.name, country?.name].filter(Boolean).join(", ");
}

// Best-effort reverse parse of an existing "City, State, Country" string
// (or legacy free-text values already in the DB) back into a cascade
// value -- used to prefill the dropdowns when editing a candidate who
// already has a value stored the old way. Falls back to all-empty if it
// can't confidently match, rather than guessing wrong.
export function parseLocation(text) {
  if (!text) return { countryCode: "", stateCode: "", city: "" };
  const parts = text.split(",").map((p) => p.trim()).filter(Boolean);
  const countryName = parts[parts.length - 1];
  const country = Country.getAllCountries().find(
    (c) => c.name.toLowerCase() === (countryName || "").toLowerCase(),
  );
  if (!country) return { countryCode: "", stateCode: "", city: "" };

  const stateName = parts.length >= 2 ? parts[parts.length - 2] : "";
  const state = stateName
    ? State.getStatesOfCountry(country.isoCode).find(
        (s) => s.name.toLowerCase() === stateName.toLowerCase(),
      )
    : null;

  const city = parts.length >= 3 ? parts[0] : "";

  return {
    countryCode: country.isoCode,
    stateCode: state?.isoCode || "",
    city: state ? city : "",
  };
}
