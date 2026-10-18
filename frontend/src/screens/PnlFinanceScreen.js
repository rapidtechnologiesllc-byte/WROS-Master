// P&L (CEO 2026-10-17): the partner & org P&L and, in the same screen, the finance operations that
// feed it (cost rates, BU P&L, reserve fund, hiring affordability, intercompany settlements,
// incentives, expenses). Each tab keeps its screen and permission (revenue / finance-operations).
import TabbedScreen from "../components/TabbedScreen";
import PnlScreen from "./PnlScreen";
import FinanceOperationsScreen from "./FinanceOperationsScreen";

const TABS = [
  { key: "pnl", label: "P&L", resource: "revenue", render: () => <PnlScreen /> },
  { key: "operations", label: "Finance Operations", resource: "finance-operations", render: () => <FinanceOperationsScreen /> },
];

export default function PnlFinanceScreen() {
  return <TabbedScreen title="P&L" tabs={TABS} />;
}
