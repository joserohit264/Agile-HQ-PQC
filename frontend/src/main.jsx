import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";

// Apply the saved theme before first paint so the sign-in screen matches it too.
try {
  const theme = localStorage.getItem("pqc_theme");
  if (theme) document.documentElement.dataset.theme = theme;
} catch { /* storage blocked */ }

createRoot(document.getElementById("root")).render(<App />);
