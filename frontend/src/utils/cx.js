// Lightweight className joiner.
export default function cx(...xs) {
  return xs.filter(Boolean).join(" ");
}
