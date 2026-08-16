// DEFECT-5: Screen-level banner for success/error messages
// Replaces toast notifications with persistent, inline banners

import { useState, useEffect } from "react";
import { AlertCircle, CheckCircle2, X } from "lucide-react";
import { Button } from "./ui";

export function useScreenBanner() {
  const [banner, setBanner] = useState(null);

  const showSuccess = (message, autoDismissMs = 3000) => {
    setBanner({ type: "success", message });
    if (autoDismissMs) {
      setTimeout(() => setBanner(null), autoDismissMs);
    }
  };

  const showError = (message) => {
    setBanner({ type: "error", message, onDismiss: () => setBanner(null) });
  };

  const showErrorWithRetry = (message, onRetry) => {
    setBanner({ type: "error", message, onRetry, onDismiss: () => setBanner(null) });
  };

  const dismiss = () => setBanner(null);

  return { banner, showSuccess, showError, showErrorWithRetry, dismiss };
}

export function ScreenLevelBanner({ type, message, onRetry, onDismiss }) {
  if (!type || !message) return null;

  if (type === "success") {
    return (
      <div className="fixed top-16 left-0 right-0 z-40 mx-auto max-w-4xl">
        <div className="mx-4 flex items-center gap-3 rounded-lg bg-emerald-50 border border-emerald-200 px-4 py-3 text-emerald-700">
          <CheckCircle2 className="h-5 w-5 flex-shrink-0" />
          <span className="flex-1 text-sm font-medium">{message}</span>
          <button
            onClick={onDismiss}
            className="text-emerald-600 hover:text-emerald-800"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>
    );
  }

  if (type === "error") {
    return (
      <div className="fixed top-16 left-0 right-0 z-40 mx-auto max-w-4xl">
        <div className="mx-4 flex items-center gap-3 rounded-lg bg-rose-50 border border-rose-200 px-4 py-3 text-rose-700">
          <AlertCircle className="h-5 w-5 flex-shrink-0" />
          <span className="flex-1 text-sm font-medium">{message}</span>
          <div className="flex gap-2">
            {onRetry && (
              <Button
                variant="ghost"
                size="sm"
                onClick={onRetry}
                className="text-rose-700 hover:bg-rose-100"
              >
                Retry
              </Button>
            )}
            <button
              onClick={onDismiss}
              className="text-rose-600 hover:text-rose-800"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    );
  }

  return null;
}
