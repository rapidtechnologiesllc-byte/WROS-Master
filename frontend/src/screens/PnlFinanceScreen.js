// P&L (CEO 2026-10-17): the partner & org P&L and, in the same screen, the finance operations that
// feed it (cost rates, BU P&L, reserve fund, hiring affordability, intercompany settlements,
// incentives, expenses) and the rate card (margin floors at placement, CEO 2026-10-23). Each tab
// keeps its screen and permission (revenue / finance-operations).
import TabbedScreen from "../components/TabbedScreen";
import PnlScreen from "./PnlScreen";
import FinanceOperationsScreen from "./FinanceOperationsScreen";
import RateCardScreen from "./RateCardScreen";

const TABS = [
  { key: "pnl", label: "P&L", resource: "revenue", render: () => <PnlScreen /> },
  { key: "operations", label: "Finance Operations", resource: "finance-operations", render: () => <FinanceOperationsScreen /> },
  { key: "rate-card", label: "Rate Card", resource: "finance-operations", render: () => <RateCardScreen /> },
];

export default function PnlFinanceScreen() {
  return <TabbedScreen title="P&L" tabs={TABS} />;
}
