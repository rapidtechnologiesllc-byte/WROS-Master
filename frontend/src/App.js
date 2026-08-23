import { BrowserRouter } from "react-router-dom";
import { ConfigProvider } from "antd";
import AppRoutes from "./routes/Approutes";
import { ThemeProvider } from "./context/ThemeContext";

// Root-cause fix for the "looks like a high school project" feedback:
// 17 files use raw, unthemed antd components (Drawer/Select/Table/
// Modal/etc.) with zero ConfigProvider anywhere in the app -- every
// one of them was rendering antd's stock blue default theme, visually
// disconnected from the BlitzenX Brand Kit v3.0 tokens
// (tailwind.config.js's bx-orange/bx-navy/bx-border/rounded-bx) the
// rest of the app already uses. One ConfigProvider here re-themes all
// 17 at once, instead of hand-editing each usage.
const BLITZENX_ANTD_THEME = {
  token: {
    colorPrimary: "#F58220", // bx-orange
    colorPrimaryHover: "#D96E14", // bx-orange-hover
    colorLink: "#F58220",
    colorLinkHover: "#D96E14",
    borderRadius: 12, // rounded-bx
    borderRadiusLG: 20, // rounded-bx-lg
    colorBorder: "#D9E2EC", // bx-border
    fontFamily:
      "Inter, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
  },
};

export default function App() {
  return (
    <ThemeProvider>
      <ConfigProvider theme={BLITZENX_ANTD_THEME}>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </ConfigProvider>
    </ThemeProvider>
  );
}
