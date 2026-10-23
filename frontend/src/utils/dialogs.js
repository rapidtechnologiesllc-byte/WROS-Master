// In-app replacements for window.confirm / window.alert, rendered by components/ConfirmHost.
// Usage: if (!(await confirmDialog("Delete this?", { danger: true }))) return;
let showDialog = null;

export function registerDialogHost(setter) {
  showDialog = setter;
  return () => {
    if (showDialog === setter) showDialog = null;
  };
}

function open(kind, message, options = {}) {
  if (!showDialog) {
    // No host mounted means a bug in App wiring: fail loudly instead of silently "cancelling"
    throw new Error('[dialogs] ConfirmHost is not mounted');
  }
  return new Promise((resolve) => {
    showDialog({
      kind,
      message,
      confirmLabel: options.confirmLabel || (options.danger ? 'Delete' : 'Continue'),
      danger: Boolean(options.danger),
      resolve,
    });
  });
}

/** Resolves true when the user confirms, false when they cancel. */
export const confirmDialog = (message, options) => open('confirm', message, options);

/** Shows a notice; resolves when the user dismisses it. */
export const alertDialog = (message) => open('alert', message);
