/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#050706",
        panel: "#0b0e0d",
        line: "#202725",
        signal: "#37c982",
        mint: "#a9e8c5",
      },
      boxShadow: {
        glow: "0 0 24px rgba(55, 201, 130, 0.09)",
      },
      fontFamily: {
        display: ["Space Grotesk", "ui-sans-serif", "system-ui", "sans-serif"],
        sans: ["DM Sans", "ui-sans-serif", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
