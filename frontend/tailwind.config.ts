import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";

const config: Config = {
  darkMode: "class",
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        // Latin first, so English takes Inter. Browsers fall through this list
        // per glyph, so Persian and Arabic -- which Inter does not cover --
        // land on Vazirmatn rather than the system's heavy Arabic fallback.
        sans: [
          "var(--font-latin)",
          "var(--font-arabic)",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif",
          "Apple Color Emoji",
          "Segoe UI Emoji",
        ],
      },

      // Every text size multiplies by --text-scale, the reader's preference,
      // so one variable resizes the whole app. Spacing stays fixed: this is a
      // text-size control, not a zoom, so tap targets keep their size.
      //
      // Line heights are unitless on purpose -- they are relative to each
      // element's own font size, so they grow with the text instead of
      // clamping it once someone picks a larger size.
      fontSize: {
        "2xs": ["calc(0.625rem * var(--text-scale))", { lineHeight: "1.4" }],
        xs: ["calc(0.6875rem * var(--text-scale))", { lineHeight: "1.4" }],
        sm: ["calc(0.8125rem * var(--text-scale))", { lineHeight: "1.45" }],
        base: ["calc(0.9375rem * var(--text-scale))", { lineHeight: "1.5" }],
        lg: ["calc(1.0625rem * var(--text-scale))", { lineHeight: "1.45" }],
        xl: ["calc(1.25rem * var(--text-scale))", { lineHeight: "1.35" }],
        "2xl": ["calc(1.5rem * var(--text-scale))", { lineHeight: "1.3" }],
      },
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        // Reaction colours, kept out of the neutral scale on purpose.
        like: "hsl(var(--like))",
        repulse: "hsl(var(--repulse))",
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
        "pop": {
          "0%": { transform: "scale(1)" },
          "45%": { transform: "scale(1.28)" },
          "100%": { transform: "scale(1)" },
        },
        "fade-up": {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "shimmer": {
          "100%": { transform: "translateX(100%)" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        pop: "pop 0.32s cubic-bezier(0.2, 0.9, 0.3, 1.4)",
        "fade-up": "fade-up 0.28s ease-out both",
        shimmer: "shimmer 1.6s infinite",
      },
    },
  },
  plugins: [animate],
};

export default config;
