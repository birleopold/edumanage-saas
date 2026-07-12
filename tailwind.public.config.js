module.exports = {
  content: [
    "./templates/base_auth.html",
    "./templates/auth/**/*.html",
    "./templates/landing.html",
    "./templates/public/**/*.html",
    "./templates/errors/**/*.html",
    "./templates/platform/**/*.html",
    "./templates/portals/public/**/*.html",
    "./templates/components/ui_public_polish.html"
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: "#eff6ff",
          100: "#dbeafe",
          600: "#2563eb",
          700: "#1d4ed8",
          900: "#1e3a8a"
        }
      }
    }
  },
  plugins: []
};
