/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        maroon: {
          DEFAULT: "#8D1B3D",
          50: "#fbeef2",
          100: "#f3d3dc",
          200: "#e3a6b6",
          300: "#d17a91",
          400: "#b8496a",
          500: "#8D1B3D",
          600: "#7a1734",
          700: "#63122a",
          800: "#4c0e20",
          900: "#360a17",
        },
        gold: {
          DEFAULT: "#FFC72C",
          50: "#fffbea",
          100: "#fff3c4",
          200: "#ffe58a",
          300: "#ffd750",
          400: "#ffc72c",
          500: "#f0ac0a",
          600: "#c98a06",
          700: "#9c6905",
          800: "#6f4a04",
          900: "#4a3103",
        },
        slateink: {
          DEFAULT: "#1E293B",
        },
        surface: {
          DEFAULT: "#F8FAFC",
        },
        govgreen: {
          DEFAULT: "#064E3B",
        },
      },
      fontFamily: {
        sans: ["Noto Sans", "Noto Sans Sinhala", "Noto Sans Tamil", "system-ui", "sans-serif"],
      },
      boxShadow: {
        gov: "0 1px 3px rgba(30, 41, 59, 0.12), 0 1px 2px rgba(30, 41, 59, 0.08)",
      },
    },
  },
  plugins: [],
}
