/* oxlint-disable react/only-export-components -- Locale provider and its hook share one context. */
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import zh from "./zh.json";

export type Locale = "en" | "zh";
export function translate(locale: Locale, text: string, values?: Record<string, string | number>) {
  const message = locale === "zh" ? (zh as Record<string, string>)[text] ?? text : text;
  return message.replace(/\{(\w+)\}/g, (match, key: string) => String(values?.[key] ?? match));
}
const LocaleContext = createContext({ locale: "en" as Locale, setLocale: (() => {}) as (locale: Locale) => void, t: (text: string, values?: Record<string, string | number>) => translate("en", text, values) });
export function LocaleProvider({ children, initialLocale }: { children: ReactNode; initialLocale?: Locale }) {
  const [locale, setLocale] = useState<Locale>(() => {
    if (initialLocale) return initialLocale;
    try {
      const saved = localStorage.getItem("labpilot-locale");
      if (saved === "en" || saved === "zh") return saved;
      return navigator.language.startsWith("zh") ? "zh" : "en";
    } catch { return "en"; }
  });
  useEffect(() => {
    document.documentElement.lang = locale === "zh" ? "zh-CN" : "en";
    document.title = locale === "zh" ? "LabPilot — 自主研究工作台" : "LabPilot — Research Control Plane";
    try { localStorage.setItem("labpilot-locale", locale); } catch { /* Storage is optional. */ }
  }, [locale]);
  const value = useMemo(() => ({ locale, setLocale, t: (text: string, values?: Record<string, string | number>) => translate(locale, text, values) }), [locale]);
  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}
export const useI18n = () => useContext(LocaleContext);
