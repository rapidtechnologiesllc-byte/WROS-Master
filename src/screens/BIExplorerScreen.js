import { useEffect, useState } from "react";
import { toast } from "react-toastify";
import { Search, Table2, ChevronDown, Download } from "lucide-react";
import { Card, Button } from "../components/ui";
import { apiRequest } from "../services/api/client";

export default function BIExplorerScreen() {
  const [tables, setTables] = useState([]);
  const [selectedTable, setSelectedTable] = useState(null);
  const [tableSchema, setTableSchema] = useState(null);
  const [selectedColumns, setSelectedColumns] = useState([]);
  const [queryResults, setQueryResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [limit, setLimit] = useState(100);
  const [offset, setOffset] = useState(0);

  // Load available tables on mount
  useEffect(() => {
    const fetchTables = async () => {
      try {
        const { data } = await apiRequest("/bi/tables", { method: "GET" });
        setTables(data?.data?.tables || []);
      } catch (err) {
        toast.error("Failed to load available tables");
      }
    };
    fetchTables();
  }, []);

  // Load table schema when table is selected
  useEffect(() => {
    if (!selectedTable) return;

    const fetchSchema = async () => {
      try {
        const { data } = await apiRequest(`/bi/tables/${selectedTable}/schema`, { method: "GET" });
        setTableSchema(data?.data);
        setSelectedColumns(data?.data?.columns || []);
        setQueryResults(null);
      } catch (err) {
        toast.error("Failed to load table schema");
      }
    };
    fetchSchema();
  }, [selectedTable]);

  const handleExecuteQuery = async () => {
    if (!selectedTable) {
      toast.warning("Please select a table");
      return;
    }

    try {
      setLoading(true);
      const params = new URLSearchParams({
        table_name: selectedTable,
        limit: limit.toString(),
        offset: offset.toString(),
      });

      if (selectedColumns.length > 0 && selectedColumns.length < (tableSchema?.columns.length || 0)) {
        selectedColumns.forEach(col => params.append("columns", col));
      }

      const { data } = await apiRequest(`/bi/query/${selectedTable}?${params}`, { method: "GET" });
      setQueryResults(data?.data);
      toast.success(`Loaded ${data?.data?.row_count || 0} rows`);
    } catch (err) {
      toast.error("Query failed");
    } finally {
      setLoading(false);
    }
  };

  const handleColumnToggle = (col) => {
    setSelectedColumns(prev =>
      prev.includes(col) ? prev.filter(c => c !== col) : [...prev, col]
    );
  };

  const toggleAllColumns = () => {
    if (selectedColumns.length === tableSchema?.columns.length) {
      setSelectedColumns([]);
    } else {
      setSelectedColumns(tableSchema?.columns || []);
    }
  };

  return (
    <div className="space-y-6 p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-gray-900">BI Explorer</h1>
        <div className="text-sm text-gray-600">Self-Service Analytics</div>
      </div>

      {/* Table Selection */}
      <Card title="Step 1: Select Table">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {tables.map(table => (
            <button
              key={table.table_name}
              onClick={() => setSelectedTable(table.table_name)}
              className={`p-4 rounded-lg border-2 transition text-left ${
                selectedTable === table.table_name
                  ? "border-blue-500 bg-blue-50"
                  : "border-gray-200 hover:border-blue-300"
              }`}
            >
              <div className="flex items-start gap-2">
                <Table2 className="h-5 w-5 text-blue-600 mt-0.5 flex-shrink-0" />
                <div>
                  <div className="font-semibold text-gray-900">{table.table_name}</div>
                  <div className="text-xs text-gray-600 mt-1">{table.columns.length} columns</div>
                </div>
              </div>
            </button>
          ))}
        </div>
      </Card>

      {/* Column Selection */}
      {selectedTable && tableSchema && (
        <Card title="Step 2: Select Columns">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="text-sm text-gray-600">
                Selected: {selectedColumns.length} of {tableSchema.columns.length}
              </div>
              <button
                onClick={toggleAllColumns}
                className="text-sm text-blue-600 hover:text-blue-700 font-medium"
              >
                {selectedColumns.length === tableSchema.columns.length ? "Deselect All" : "Select All"}
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {tableSchema.columns.map(col => (
                <label key={col} className="flex items-center gap-2 p-2 rounded hover:bg-gray-50 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selectedColumns.includes(col)}
                    onChange={() => handleColumnToggle(col)}
                    className="rounded"
                  />
                  <span className="text-sm font-mono text-gray-700">{col}</span>
                </label>
              ))}
            </div>
          </div>
        </Card>
      )}

      {/* Query Options */}
      {selectedTable && (
        <Card title="Step 3: Configure Query">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">Limit (Rows)</label>
              <input
                type="number"
                value={limit}
                onChange={(e) => setLimit(Math.min(parseInt(e.target.value) || 100, 1000))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                min="1"
                max="1000"
              />
            </div>
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">Offset (Page)</label>
              <input
                type="number"
                value={offset}
                onChange={(e) => setOffset(Math.max(parseInt(e.target.value) || 0, 0))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                min="0"
              />
            </div>
          </div>

          <Button
            onClick={handleExecuteQuery}
            disabled={loading || !selectedTable}
            className="w-full mt-4"
          >
            {loading ? "Executing..." : "Execute Query"}
          </Button>
        </Card>
      )}

      {/* Results */}
      {queryResults && (
        <Card title={`Results: ${selectedTable}`}>
          <div className="space-y-4">
            <div className="flex items-center justify-between text-sm text-gray-600">
              <div>{queryResults.row_count} rows returned</div>
              <div>Showing rows {offset + 1} to {offset + queryResults.row_count}</div>
            </div>

            {queryResults.row_count > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-gray-50">
                      {queryResults.columns_requested.map(col => (
                        <th key={col} className="text-left py-2 px-3 font-semibold text-gray-700">
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {queryResults.rows.map((row, idx) => (
                      <tr key={idx} className="border-b hover:bg-gray-50">
                        {queryResults.columns_requested.map(col => (
                          <td key={`${idx}-${col}`} className="py-2 px-3 text-gray-700">
                            {row[col] !== null && row[col] !== undefined
                              ? String(row[col]).substring(0, 100)
                              : "—"}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-center text-gray-600 py-4">No rows found</div>
            )}

            {/* Pagination */}
            <div className="flex gap-2 pt-4 border-t">
              <Button
                variant="secondary"
                onClick={() => setOffset(Math.max(0, offset - limit))}
                disabled={offset === 0}
              >
                ← Previous
              </Button>
              <Button
                variant="secondary"
                onClick={() => setOffset(offset + limit)}
                disabled={queryResults.row_count < limit}
              >
                Next →
              </Button>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
