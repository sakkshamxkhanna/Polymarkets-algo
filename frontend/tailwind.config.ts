import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        "bg-primary":   "#07090d",
        "bg-secondary": "#0d1117",
        "bg-tertiary":  "#131922",
        "bg-elevated":  "#1a2230",
        "bg-card":      "#0e1419",
        "bg-hover":     "#161e2a",

        "border-faint":   "#161c26",
        "border-dim":     "#1c2330",
        "border-primary": "#232c3a",
        "border-strong":  "#303a4c",

        "text-primary":   "#e8ebf2",
        "text-secondary": "#a8b0c0",
        "text-muted":     "#7a8497",
        "text-dim":       "#525c70",
        "text-faint":     "#363f51",

        "accent-cyan":      "#00d9ff",
        "accent-cyan-dim":  "#0099b8",
        "accent-amber":     "#ffb547",
        "accent-amber-dim": "#cc8a2b",
        "accent-green":     "#00d488",
        "accent-green-dim": "#00946a",
        "accent-red":       "#ff3b5c",
        "accent-red-dim":   "#b8253f",
        "accent-yellow":    "#ffd84d",
        "accent-purple":    "#a78bfa",
        "accent-blue":      "#5fa8ff",
      },
      fontFamily: {
        mono:    ["var(--font-jetbrains-mono)", "'IBM Plex Mono'", "Consolas", "monospace"],
        sans:    ["var(--font-ibm-plex)", "system-ui", "sans-serif"],
        display: ["var(--font-ibm-plex-condensed)", "var(--font-ibm-plex)", "sans-serif"],
      },
      fontSize: {
        "2xs": ["10px", { lineHeight: "12px" }],
        "3xs": ["9px",  { lineHeight: "11px" }],
      },
      letterSpacing: {
        term: "0.04em",
      },
      animation: {
        "fade-in":  "fadeIn 0.25s ease-out",
        "slide-up": "slideUp 0.25s ease-out",
        "flash-up": "flashUp 0.6s ease-out",
        "flash-dn": "flashDn 0.6s ease-out",
        "blink":    "blink 1.4s ease-in-out infinite",
      },
      keyframes: {
        fadeIn:  { "0%": { opacity: "0" }, "100%": { opacity: "1" } },
        slideUp: { "0%": { transform: "translateY(4px)", opacity: "0" }, "100%": { transform: "translateY(0)", opacity: "1" } },
        flashUp: { "0%": { backgroundColor: "rgba(0, 212, 136, 0.28)" }, "100%": { backgroundColor: "transparent" } },
        flashDn: { "0%": { backgroundColor: "rgba(255, 59, 92, 0.28)" }, "100%": { backgroundColor: "transparent" } },
        blink:   { "0%, 50%, 100%": { opacity: "1" }, "25%, 75%": { opacity: "0.35" } },
        pulseDot: { "0%, 100%": { opacity: "1" }, "50%": { opacity: "0.4" } },
      },
      boxShadow: {
        "panel":      "0 1px 0 rgba(255,255,255,0.02) inset, 0 12px 32px -16px rgba(0,0,0,0.6)",
        "inset-line": "inset 0 -1px 0 rgba(35, 44, 58, 0.6)",
        "glow-cyan":  "0 0 24px -4px rgba(0, 217, 255, 0.45)",
        "glow-amber": "0 0 24px -4px rgba(255, 181, 71, 0.5)",
      },
    },
  },
  plugins: [],
};

export default config;
