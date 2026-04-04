/** @jsxImportSource preact */
import { useEffect, useState } from "preact/hooks";

interface UseThemeResult {
  oledTheme: boolean;
  setOledTheme: (value: boolean) => void;
}

export function useTheme(): UseThemeResult {
  const [oledTheme, setOledTheme] = useState<boolean>(() => {
    try {
      return window.localStorage.getItem("theme") === "oled";
    } catch {
      return false;
    }
  });

  useEffect(() => {
    if (oledTheme) {
      document.documentElement.dataset.theme = "oled";
      window.localStorage.setItem("theme", "oled");
      return;
    }
    delete document.documentElement.dataset.theme;
    window.localStorage.setItem("theme", "default");
  }, [oledTheme]);

  return {
    oledTheme,
    setOledTheme
  };
}
