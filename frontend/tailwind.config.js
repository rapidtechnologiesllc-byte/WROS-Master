/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: ["./src/**/*.{js,jsx}", "./public/index.html"],
  theme: {
    extend: {
      // BlitzenX Brand Kit v3.0
      colors: {
        "bx-orange": {
          DEFAULT: "#F58220",
          hover: "#D96E14",
        },
        "bx-navy": "#0B1F3A",
        "bx-slate": "#2E3A4D",
        "bx-light": "#F4F6F8",
        "bx-border": "#D9E2EC",
      },
      fontFamily: {
        sans: [
          "Inter",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "sans-serif",
        ],
      },
      borderRadius: {
        bx: "12px",
        "bx-lg": "20px",
      },
    },
  },
  plugins: []
};
