// Shared button component with variants.
import cx from "../../utils/cx";

export default function Button({
  children,
  onClick,
  variant = "primary",
  disabled,
  className
}) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-xl px-3.5 py-2 text-sm font-semibold transition focus:outline-none focus:ring-2 focus:ring-offset-2";
  const styles = {
    primary:
      "bg-gray-900 text-white hover:bg-gray-800 focus:ring-gray-900 disabled:bg-gray-400",
    secondary:
      "bg-gray-100 text-gray-900 hover:bg-gray-200 focus:ring-gray-300 disabled:opacity-60",
    ghost:
      "bg-transparent text-gray-900 hover:bg-gray-100 focus:ring-gray-300 disabled:opacity-60",
    danger:
      "bg-red-600 text-white hover:bg-red-700 focus:ring-red-500 disabled:opacity-60",
    success:
      "bg-emerald-600 text-white hover:bg-emerald-700 focus:ring-emerald-500 disabled:opacity-60"
  };

  return (
    <button
      className={cx(base, styles[variant], className)}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
}
