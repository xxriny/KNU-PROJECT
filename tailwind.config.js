/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // 다크 테마 — 기존 CustomTkinter 테마와 일관성 유지
        slate: {
          850: "#141c2e",
          950: "#0b1120",
        },
      },
      fontFamily: {
        sans: ["Pretendard", "Inter", "system-ui", "sans-serif"],
        display: ["Inter", "system-ui", "sans-serif"],
        mono: ["\"JetBrains Mono\"", "\"Fira Code\"", "monospace"],
      },
    },
  },
  plugins: [],
};
