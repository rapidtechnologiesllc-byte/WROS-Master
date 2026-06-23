import { BrowserRouter } from "react-router-dom";
import AppRoutes from "./routes/Approutes";

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}
