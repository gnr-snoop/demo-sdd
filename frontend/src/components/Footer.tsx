import React from "react";

// Footer — dark navy de Claude (guía §4.9) + logo monocromo (§4.0).
// Estructura: <footer class="footer"><div class="container"> logo + credits.
const Footer: React.FC = () => {
  const year = new Date().getFullYear();
  return (
    <footer className="footer">
      <div className="container">
        {/* Logo monocromo — filter invert(1) brightness(2) → blanco sobre #181715 (§4.0) */}
        <a href="/" className="footer-logo" aria-label="Snoop Consulting">
          <img src="logo-snoop-black.svg" alt="Snoop Consulting" width="120" height="28" />
        </a>
        <p className="credits">
          © {year} Snoop Consulting · Face Insight Demo · Especificación SDD
        </p>
      </div>
    </footer>
  );
};

export default Footer;
