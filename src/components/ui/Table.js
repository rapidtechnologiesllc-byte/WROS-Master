// Simple table renderer for lists.
import cx from "../../utils/cx";

export default function Table({ columns, rows }) {
  return (
    <div className="overflow-visible rounded-2xl border">
      <table className="w-full text-left text-sm">
        <thead className="bg-gray-50">
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                className={cx(
                  "px-4 py-3 text-xs font-semibold text-gray-700",
                  c.className,
                )}
              >
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y bg-white">
          {rows.map((r, idx) => (
            <tr key={idx} className="hover:bg-gray-50">
              {columns.map((c) => (
                <td key={c.key} className="px-4 py-3 text-gray-900">
                  {r[c.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
