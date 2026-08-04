/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: "#2A5B8C",
          50: "#eaf1f8",
          100: "#cfe0ee",
          200: "#a3c3dd",
          300: "#76a5cb",
          400: "#4d87b9",
          500: "#2A5B8C",
          600: "#224a72",
          700: "#1a3958",
          800: "#12283f",
          900: "#0b1a29",
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
        sans: ["Noto Sans", "system-ui", "sans-serif"],
      },
      boxShadow: {
        gov: "0 1px 3px rgba(30, 41, 59, 0.12), 0 1px 2px rgba(30, 41, 59, 0.08)",
      },
    },
  },
  plugins: [],
}
