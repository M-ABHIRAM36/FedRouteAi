/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#0d1117", // GitHub / TensorBoard dark style
        surface: "#161b22",
        surfaceHover: "#21262d",
        border: "#30363d",
        textPrimary: "#c9d1d9",
        textSecondary: "#8b949e",
        primary: "#2f81f7",     // Blue
        primaryHover: "#388bfd",
        success: "#238636",     // Green
        warning: "#d29922",     // Yellow
        danger: "#f85149",      // Red
        accent: "#8957e5",      // Purple
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Arial', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'Liberation Mono', 'Courier New', 'monospace'],
      },
    },
  },
  plugins: [],
}
