// A screen made of other screens, one tab each (the merged menu items, CEO 2026-10-17). A tab is
// shown only when the role template may view the resource its API checks, so merging screens
// never widens or narrows what anyone can open. The active tab lives in ?view=<key>, which is
// where each retired route redirects.
import { hasPermission } from "../utils/permissionsRoleTemplate";
import useTabParam from "../utils/useTabParam";
import cx from "../utils/cx";

export default function TabbedScreen({ title, subtitle, tabs }) {
  const visible = tabs.filter((tab) => hasPermission(tab.resource, "view"));
  const [activeKey, setActiveKey] = useTabParam(visible.map((tab) => tab.key), "view");
  const active = visible.find((tab) => tab.key === activeKey);

  if (!visible.length) {
    return (
      <div className="rounded-2xl border bg-white p-6 text-sm text-gray-600">
        Your role does not include any part of {title}. Ask an administrator to grant it in Role Templates.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{title}</h1>
        {subtitle && <p className="text-sm text-gray-500">{subtitle}</p>}
      </div>
      {visible.length > 1 && (
        <div className="flex flex-wrap gap-2 border-b pb-2" role="tablist">
          {visible.map((tab) => (
            <button
              key={tab.key}
              role="tab"
              aria-selected={tab.key === active.key}
              onClick={() => setActiveKey(tab.key)}
              className={cx(
                "rounded-lg px-4 py-2 text-sm font-semibold transition",
                tab.key === active.key ? "bg-bx-navy text-white" : "text-gray-600 hover:bg-gray-100",
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
      )}
      <div key={active.key}>{active.render()}</div>
    </div>
  );
}
