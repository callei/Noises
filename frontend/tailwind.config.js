/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--bg-color)",
        panel: "var(--panel-color)",
        primary: "var(--accent-color)",
        "primary-hover": "var(--accent-hover)",
      }
    },
  },
  plugins: [],
}
