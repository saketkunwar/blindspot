"use client";
import { useEffect, useState } from "react";

export default function ThemeToggle() {
  const [light, setLight] = useState(true);
  useEffect(() => {
    try {
      const saved = window.localStorage.getItem("bs-theme");
      if (saved === "dark") setLight(false);
    } catch { /* default light */ }
  }, []);
  useEffect(() => {
    try {
      document.body.classList.toggle("light", light);
      window.localStorage.setItem("bs-theme", light ? "light" : "dark");
    } catch { /* noop */ }
  }, [light]);
  return (
    <button type="button" className="themebtn" onClick={() => setLight((v) => !v)}>
      {light ? "Dark" : "Light"}
    </button>
  );
}
