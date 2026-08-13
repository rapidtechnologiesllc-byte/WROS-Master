// DEFECT-5: Screen-Level Error/Success Banners (replaces toasts)
import { useEffect, useState } from "react";
import { CheckCircle2, AlertCircle, X } from "lucide-react";
import { Button } from "./ui";

export function ScreenLevelBanner({ type, message, onDismiss, onRetry, autoDismissMs = 5000 }) {
  useEffect(() => {
    if (type === "success" && autoDismissMs) {
      const timer = setTimeout(onDismiss, autoDismissMs);
      return () => clearTimeout(timer);
    }
  }, [type, autoDismissMs, onDismiss]);

  if (!message) return null;

  const isSuccess = type === "success";
  const bgClass = isSuccess
    ? "bg-emerald-50 border-emerald-200"
    : "bg-rose-50 border-rose-200";
  const textClass = isSuccess
    ? "text-emerald-700"
    : "text-rose-700";
  const iconClass = isSuccess
    ? "text-emerald-600"
    : "text-rose-600";

  return (
    <div className={`fixed top-16 left-0 right-0 border-b ${bgClass} z-40 px-6 py-3`}>
      <div className={`max-w-6xl mx-auto flex items-center gap-3 ${textClass}`}>
        {isSuccess ? (
          <CheckCircle2 className={`h-5 w-5 flex-shrink-0 ${iconClass}`} />
        ) : (
          <AlertCircle className={`h-5 w-5 flex-shrink-0 ${iconClass}`} />
        )}

        <div className="flex-1">
          <p className="text-sm font-medium">{message}</p>
        </div>

        {onRetry && !isSuccess && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onRetry}
            className="text-xs"
          >
            Retry
          </Button>
        )}

        <button
          onClick={onDismiss}
          className={`flex-shrink-0 ${textClass} hover:opacity-70`}
        >
          <X className="h-5 w-5" />
        </button>
      </div>
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
