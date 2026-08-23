// Simple table renderer for lists.
import cx from "../../utils/cx";

export default function Table({ columns = [], rows = [], data = [] }) {
  // Support both 'rows' and 'data' parameter names
  const tableData = data.length > 0 ? data : rows;

  return (
    <div className="overflow-visible rounded-2xl border">
      <table className="w-full text-left text-sm">
        <thead className="bg-gray-50">
          <tr>
            {columns.map((c, i) => (
              <th
                key={c.key || c.accessor || c.header || `col_${i}`}
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
          {tableData.map((r, idx) => (
            <tr key={r.id || r.user_id || `row_${idx}`} className="hover:bg-gray-50">
              {columns.map((c, cIdx) => (
                <td key={`${c.key || c.accessor || c.header || `col_${cIdx}`}_${idx}`} className="px-4 py-3 text-gray-900">
                  {c.cell ? c.cell(r) : r[c.accessor || c.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
