import { useNavigate } from "react-router-dom";
import { ROUTES } from "../../utils/Routes";

export default function LocaleSection({ panel, loading }) {
  const navigate = useNavigate();

  if (loading) return <div className="text-sm text-gray-500">Loading...</div>;
  if (!panel || !panel.LOCALE) return <div className="text-sm text-gray-400">No locale settings available.</div>;

  const locale = panel.LOCALE;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 text-sm sm:grid-cols-3">
        <div>
          <div className="text-xs font-semibold text-gray-500">Timezone</div>
          <div className="mt-0.5 text-gray-900">{locale.default_timezone}</div>
        </div>
        <div>
          <div className="text-xs font-semibold text-gray-500">Date Format</div>
          <div className="mt-0.5 text-gray-900">{locale.default_date_format}</div>
        </div>
        <div>
          <div className="text-xs font-semibold text-gray-500">Currency</div>
          <div className="mt-0.5 text-gray-900">{locale.default_currency}</div>
        </div>
      </div>
      <button
        type="button"
        onClick={() => navigate(ROUTES.TENANT_LOCALE)}
        className="rounded-lg bg-bx-orange px-3.5 py-2 text-sm font-semibold text-white hover:bg-bx-orange-hover"
      >
        Manage Locale & Currency
      </button>
    </div>
  );
}
