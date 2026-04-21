// React app bootstrap.
import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import 'antd/dist/antd.css';

const container = document.getElementById("root");
const root = createRoot(container);

root.render(
  <React.StrictMode>
      <App />
  </React.StrictMode>
);
