/** @jsxImportSource preact */
import { useEffect, useState } from "preact/hooks";

interface UseThemeResult {
  oledTheme: boolean;
  setOledTheme: (value: boolean) => void;
}

export function useTheme(): UseThemeResult {
  const [oledTheme, setOledTheme] = useState<boolean>(() => {
    try {
      const storedTheme = window.localStorage.getItem("theme");
      if (storedTheme === "default") {
        return false;
      }
      return true;
    } catch {
      return true;
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
