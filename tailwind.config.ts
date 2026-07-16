import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          primary: "#0F0F0F",
          secondary: "#181818",
          tertiary: "#212121",
          hover: "#2A2A2A",
        },
        accent: {
          DEFAULT: "#4A9EFF",
          hover: "#3A8AEF",
          subtle: "rgba(74, 158, 255, 0.1)",
        },
        fg: {
          DEFAULT: "#ECECEC",
          muted: "#9A9A9A",
          subtle: "#6B6B6B",
        },
        border: {
          DEFAULT: "#2A2A2A",
          subtle: "#1F1F1F",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-jetbrains-mono)", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
