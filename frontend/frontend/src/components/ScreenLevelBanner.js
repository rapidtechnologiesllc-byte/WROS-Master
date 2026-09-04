// DEFECT-5: Inline Validation Summary (replaces toasts)
import { useEffect, useState } from "react";
import { CheckCircle2, AlertCircle } from "lucide-react";

export function ValidationSummary({ errors, onFieldClick }) {
  if (!errors || Object.keys(errors).length === 0) return null;

  const errorFields = Object.entries(errors).map(([field, message]) => ({ field, message }));

  return (
    <div className="mb-4 rounded-xl border border-red-200 bg-red-50 p-4 animate-slide-down">
      <div className="flex gap-3">
        <AlertCircle className="h-5 w-5 flex-shrink-0 text-red-600 mt-0.5" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-red-800 mb-2">
            {errorFields.length} field{errorFields.length > 1 ? 's' : ''} required
          </p>
          <div className="flex flex-wrap gap-2">
            {errorFields.map(({ field, message }) => (
              <button
                key={field}
                onClick={() => onFieldClick?.(field)}
                className="text-xs font-medium text-red-700 hover:text-red-900 hover:underline px-2 py-1 rounded hover:bg-red-100 transition-colors"
              >
                {message.replace(' is required.', '').trim()}
              </button>
            ))}
          </div>
        </div>
      </div>

      <style>{`
        @keyframes slide-down {
          from {
            transform: translateY(-10px);
            opacity: 0;
          }
          to {
            transform: translateY(0);
            opacity: 1;
          }
        }
        .animate-slide-down {
          animation: slide-down 0.25s ease-out;
        }
      `}</style>
    </div>
  );
}

// Toast-replacement for success/API errors (still needed for global messages)
export function ScreenLevelBanner({ type, message, onDismiss, onRetry, autoDismissMs = 5000 }) {
  useEffect(() => {
    if (type === "success" && autoDismissMs) {
      const timer = setTimeout(onDismiss, autoDismissMs);
      return () => clearTimeout(timer);
    }
  }, [type, autoDismissMs, onDismiss]);

  if (!message) return null;

  const isSuccess = type === "success";
  const bgClass = isSuccess ? "bg-emerald-500" : "bg-red-500";
  const hoverClass = isSuccess ? "hover:bg-emerald-600" : "hover:bg-red-600";

  return (
    <div className={`fixed top-16 left-0 right-0 ${bgClass} z-50 px-4 py-2.5 animate-slide-down`}>
      <div className="max-w-7xl mx-auto flex items-center justify-between gap-3 text-white">
        <div className="flex items-center gap-2.5 flex-1 min-w-0">
          {isSuccess ? (
            <CheckCircle2 className="h-4 w-4" />
          ) : (
            <AlertCircle className="h-4 w-4" />
          )}
          <p className="text-xs font-medium truncate">{message}</p>
        </div>

        <div className="flex-shrink-0 flex items-center gap-1.5">
          {onRetry && !isSuccess && (
            <button
              onClick={onRetry}
              className={`text-xs font-semibold px-2.5 py-1 rounded transition-colors ${hoverClass}`}
            >
              Retry
            </button>
          )}
          <button
            onClick={onDismiss}
            className={`flex-shrink-0 p-0.5 rounded transition-colors opacity-80 hover:opacity-100 ${hoverClass}`}
            aria-label="Dismiss message"
          >
            ✕
          </button>
        </div>
      </div>

      <style>{`
        @keyframes slide-down {
          from {
            transform: translateY(-10px);
            opacity: 0;
          }
          to {
            transform: translateY(0);
            opacity: 1;
          }
        }
        .animate-slide-down {
          animation: slide-down 0.25s ease-out;
        }
      `}</style>
    </div>
  );
}

// Hook for managing banner state
export function useScreenBanner() {
  const [banner, setBanner] = useState(null);

  const showSuccess = (message) => {
    setBanner({ type: "success", message });
  };

  const showError = (message) => {
    setBanner({ type: "error", message });
  };

  const dismiss = () => {
    setBanner(null);
  };

  return {
    banner,
    showSuccess,
    showError,
    dismiss,
  };
}
