"""Landing page module for Sektoral.

Renders the Indonesian standalone HTML landing page for the Sectoral local
equity research product.
"""
from __future__ import annotations

import base64
from pathlib import Path

_FONTS_DIR = Path(__file__).resolve().parent / "assets" / "fonts"


def _embedded_font(filename: str) -> str:
    font_path = _FONTS_DIR / filename
    try:
        encoded = base64.b64encode(font_path.read_bytes()).decode("ascii")
    except OSError:
        return ""
    return f"data:font/ttf;base64,{encoded}"


def render_landing() -> str:
    """Render the standalone Indonesian HTML landing page for Sektoral."""
    rob_reg = _embedded_font("Roboto-Regular.ttf")
    rob_bold = _embedded_font("Roboto-Bold.ttf")
    rob_ita = _embedded_font("Roboto-Italic.ttf")

    font_faces = ""
    if rob_reg:
        font_faces += (
            f"@font-face {{ font-family: 'Roboto'; src: url('{rob_reg}') format('truetype'); "
            f"font-weight: 400; font-style: normal; font-display: swap; }}\n"
        )
    if rob_bold:
        font_faces += (
            f"@font-face {{ font-family: 'Roboto'; src: url('{rob_bold}') format('truetype'); "
            f"font-weight: 700; font-style: normal; font-display: swap; }}\n"
            f"@font-face {{ font-family: 'Roboto'; src: url('{rob_bold}') format('truetype'); "
            f"font-weight: 800; font-style: normal; font-display: swap; }}\n"
            f"@font-face {{ font-family: 'Roboto'; src: url('{rob_bold}') format('truetype'); "
            f"font-weight: 900; font-style: normal; font-display: swap; }}\n"
        )
    if rob_ita:
        font_faces += (
            f"@font-face {{ font-family: 'Roboto'; src: url('{rob_ita}') format('truetype'); "
            f"font-weight: 400; font-style: italic; font-display: swap; }}\n"
        )

    css_styles = f"""
{font_faces}
:root {{
  --color-primary: #0928B1;
  --color-primary-hover: #071F8A;
  --color-primary-light: #EEF2FF;
  --color-white: #FFFFFF;
  --color-charcoal: #333333;
  --color-muted: #555555;
  --color-rule: #D9D9D9;
  --color-rule-light: #EFEFEF;
  --color-table-tint: #B4C7FF;
  --color-table-row: #F4F7FF;
  --color-surface-bg: #F8F9FA;
  --color-accent-teal: #1DCD9F;
  --color-accent-green: #3ED628;
  --color-accent-blue-deep: #0047AB;
  --color-accent-blue-soft: #7596FF;
  --color-partial-bg: #FFF8E6;
  --color-partial-border: #F0B429;
  --color-partial-text: #744210;
  --color-valid-bg: #E6FFFA;
  --color-valid-border: #38B2AC;
  --color-valid-text: #234E52;
  --font-main: 'Roboto', -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
  --font-mono: ui-monospace, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace;
}}

*, *::before, *::after {{
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}}

html {{
  scroll-behavior: smooth;
  font-size: 16px;
  background-color: var(--color-white);
  color: var(--color-charcoal);
  font-family: var(--font-main);
}}

body {{
  font-family: var(--font-main);
  color: var(--color-charcoal);
  background-color: var(--color-white);
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}}

/* Accessibility Focus & Skip Link */
:focus-visible {{
  outline: 3px solid var(--color-primary);
  outline-offset: 2px;
}}

.skip-link {{
  position: absolute;
  top: -40px;
  left: 16px;
  background: var(--color-primary);
  color: var(--color-white);
  padding: 8px 16px;
  z-index: 1000;
  font-weight: 700;
  text-decoration: none;
  border-radius: 0 0 4px 4px;
  transition: top 0.15s ease-in-out;
}}

.skip-link:focus {{
  top: 0;
}}

/* Layout Containers */
.container {{
  width: 100%;
  max-width: 1160px;
  margin-left: auto;
  margin-right: auto;
  padding-left: 24px;
  padding-right: 24px;
}}

/* Header & Navigation */
.site-header {{
  background-color: var(--color-white);
  border-bottom: 1px solid var(--color-rule);
  position: sticky;
  top: 0;
  z-index: 100;
}}

.header-container {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 16px;
  padding-bottom: 16px;
  max-width: 1160px;
  margin-left: auto;
  margin-right: auto;
  padding-left: 24px;
  padding-right: 24px;
}}

.brand-link {{
  display: inline-flex;
  align-items: center;
  text-decoration: none;
}}

.brand-logo {{
  display: block;
  height: 34px;
  width: auto;
}}

.site-nav {{
  display: flex;
  align-items: center;
  gap: 24px;
}}

.nav-link {{
  color: var(--color-charcoal);
  text-decoration: none;
  font-size: 14.5px;
  font-weight: 700;
  transition: color 0.15s ease;
}}

.nav-link:hover {{
  color: var(--color-primary);
  text-decoration: underline;
  text-underline-offset: 4px;
}}

.nav-cta {{
  display: inline-block;
  background-color: var(--color-primary);
  color: var(--color-white);
  text-decoration: none;
  font-size: 14px;
  font-weight: 700;
  padding: 9px 18px;
  border-radius: 6px;
  border: 1px solid var(--color-primary);
  transition: background-color 0.15s ease, border-color 0.15s ease;
}}

.nav-cta:hover {{
  background-color: var(--color-primary-hover);
  border-color: var(--color-primary-hover);
}}

/* Hero Section (First Viewport) */
.hero-section {{
  background-color: var(--color-white);
  padding-top: 48px;
  padding-bottom: 64px;
  border-bottom: 1px solid var(--color-rule);
}}

.hero-container {{
  display: grid;
  grid-template-columns: 1.15fr 0.85fr;
  gap: 48px;
  align-items: start;
  max-width: 1160px;
  margin-left: auto;
  margin-right: auto;
  padding-left: 24px;
  padding-right: 24px;
}}

.hero-content {{
  display: flex;
  flex-direction: column;
  gap: 20px;
}}

.kicker-badge {{
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background-color: var(--color-surface-bg);
  border: 1px solid var(--color-rule);
  padding: 4px 12px;
  border-radius: 4px;
  width: fit-content;
}}

.badge-indicator {{
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: var(--color-accent-teal);
  display: inline-block;
}}

.kicker-text {{
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--color-primary);
}}

.hero-title {{
  font-size: 38px;
  line-height: 1.22;
  font-weight: 800;
  color: var(--color-primary);
  letter-spacing: -0.02em;
}}

.hero-lead {{
  font-size: 17px;
  line-height: 1.55;
  color: var(--color-charcoal);
}}

.cta-group {{
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 4px;
  flex-wrap: wrap;
}}

.btn {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  font-weight: 700;
  padding: 12px 24px;
  border-radius: 6px;
  text-decoration: none;
  cursor: pointer;
  transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease;
  line-height: 1.4;
}}

.btn-primary {{
  background-color: var(--color-primary);
  color: var(--color-white);
  border: 2px solid var(--color-primary);
}}

.btn-primary:hover {{
  background-color: var(--color-primary-hover);
  border-color: var(--color-primary-hover);
}}

.btn-secondary {{
  background-color: var(--color-white);
  color: var(--color-primary);
  border: 2px solid var(--color-rule);
}}

.btn-secondary:hover {{
  border-color: var(--color-primary);
  background-color: var(--color-primary-light);
}}

.btn-large {{
  padding: 14px 28px;
  font-size: 16px;
}}

/* Adjacent Disclosure Box (Hero) */
.disclosure-box {{
  margin-top: 12px;
  background-color: var(--color-surface-bg);
  border: 1px solid var(--color-rule);
  border-left: 4px solid var(--color-primary);
  padding: 16px 18px;
  border-radius: 4px;
}}

.disclosure-header {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  border-bottom: 1px solid var(--color-rule-light);
  padding-bottom: 6px;
}}

.disclosure-tag {{
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-primary);
}}

.disclosure-mode {{
  font-size: 11px;
  font-weight: 700;
  color: var(--color-muted);
  font-family: var(--font-mono);
}}

.disclosure-list {{
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
}}

.disclosure-list li {{
  font-size: 12.5px;
  line-height: 1.45;
  color: var(--color-charcoal);
}}

.disclosure-list code {{
  font-family: var(--font-mono);
  font-size: 11.5px;
  background-color: #EAEAEA;
  padding: 1px 4px;
  border-radius: 3px;
}}

/* Right Column: Instrument Frame */
.hero-instrument {{
  display: flex;
  flex-direction: column;
}}

.instrument-panel {{
  background-color: var(--color-white);
  border: 1px solid var(--color-rule);
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  overflow: hidden;
}}

.instrument-bar {{
  background-color: var(--color-surface-bg);
  border-bottom: 1px solid var(--color-rule);
  padding: 10px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}}

.instrument-title-group {{
  display: flex;
  align-items: center;
  gap: 8px;
}}

.instrument-dot {{
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background-color: var(--color-accent-green);
  display: inline-block;
}}

.instrument-heading {{
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-charcoal);
}}

.instrument-status-tag {{
  font-size: 11px;
  font-weight: 700;
  color: var(--color-primary);
  background-color: var(--color-table-tint);
  padding: 2px 8px;
  border-radius: 3px;
}}

.flow-figure {{
  padding: 18px 18px 12px;
  background-color: var(--color-white);
  text-align: center;
}}

.flow-preview-img {{
  display: block;
  max-width: 100%;
  height: auto;
  border: 1px solid var(--color-rule);
  border-radius: 4px;
  background-color: #FAFAFA;
  margin: 0 auto;
}}

.flow-caption {{
  margin-top: 10px;
  font-size: 11.5px;
  color: var(--color-muted);
  line-height: 1.4;
  font-style: italic;
}}

.instrument-metrics {{
  border-top: 1px solid var(--color-rule);
  background-color: var(--color-surface-bg);
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}}

.metric-row {{
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  font-size: 12px;
  border-bottom: 1px dotted var(--color-rule);
  padding-bottom: 4px;
}}

.metric-row:last-child {{
  border-bottom: none;
  padding-bottom: 0;
}}

.metric-label {{
  color: var(--color-muted);
  font-weight: 700;
}}

.metric-value {{
  font-family: var(--font-mono);
  font-size: 11.5px;
  color: var(--color-charcoal);
  font-weight: 600;
}}

.metric-value-valid {{
  font-family: var(--font-mono);
  font-size: 11.5px;
  color: var(--color-valid-text);
  font-weight: 700;
  background-color: var(--color-valid-bg);
  padding: 1px 6px;
  border-radius: 3px;
  border: 1px solid var(--color-valid-border);
}}

.metric-value-partial {{
  font-family: var(--font-mono);
  font-size: 11.5px;
  color: var(--color-partial-text);
  font-weight: 700;
  background-color: var(--color-partial-bg);
  padding: 1px 6px;
  border-radius: 3px;
  border: 1px solid var(--color-partial-border);
}}

/* Shared Section Styles */
.section-block {{
  padding-top: 64px;
  padding-bottom: 64px;
}}

.section-bordered {{
  border-bottom: 1px solid var(--color-rule);
}}

.section-intro {{
  max-width: 760px;
  margin-bottom: 40px;
}}

.section-kicker {{
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-primary);
  display: block;
  margin-bottom: 8px;
}}

.section-heading {{
  font-size: 28px;
  line-height: 1.3;
  font-weight: 800;
  color: var(--color-charcoal);
  margin-bottom: 12px;
  letter-spacing: -0.01em;
}}

.section-desc {{
  font-size: 16px;
  color: var(--color-muted);
  line-height: 1.6;
}}

/* Workflow (Cara Kerja) Signature Interaction */
.interactive-steps {{
  display: flex;
  flex-direction: column;
  gap: 16px;
}}

.step-card {{
  background-color: var(--color-white);
  border: 1px solid var(--color-rule);
  border-radius: 6px;
  overflow: hidden;
  transition: border-color 0.15s ease;
}}

.step-card[open] {{
  border-color: var(--color-primary);
}}

.step-header {{
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 18px 24px;
  background-color: var(--color-surface-bg);
  cursor: pointer;
  list-style: none;
  user-select: none;
  border-bottom: 1px solid transparent;
}}

.step-header::-webkit-details-marker {{
  display: none;
}}

.step-card[open] .step-header {{
  border-bottom: 1px solid var(--color-rule);
  background-color: var(--color-primary-light);
}}

.step-badge {{
  background-color: var(--color-primary);
  color: var(--color-white);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.05em;
  padding: 4px 10px;
  border-radius: 4px;
  white-space: nowrap;
}}

.step-header-text {{
  flex: 1;
}}

.step-title {{
  font-size: 17px;
  font-weight: 800;
  color: var(--color-charcoal);
  margin-bottom: 2px;
}}

.step-summary {{
  font-size: 13.5px;
  color: var(--color-muted);
  line-height: 1.4;
}}

.step-toggle-icon {{
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-primary);
  font-weight: 800;
  font-size: 18px;
}}

.step-toggle-icon::before {{
  content: '+';
}}

.step-card[open] .step-toggle-icon::before {{
  content: '−';
}}

.step-body {{
  padding: 24px;
  background-color: var(--color-white);
}}

.step-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 28px;
}}

.step-subheading {{
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--color-primary);
  margin-bottom: 8px;
}}

.step-detail-col p {{
  font-size: 14px;
  line-height: 1.55;
  color: var(--color-charcoal);
}}

.step-detail-col code {{
  font-family: var(--font-mono);
  font-size: 12.5px;
  background-color: #EAEAEA;
  padding: 1px 4px;
  border-radius: 3px;
}}

.step-list {{
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
}}

.step-list li {{
  font-size: 14px;
  line-height: 1.5;
  color: var(--color-charcoal);
  position: relative;
  padding-left: 18px;
}}

.step-list li::before {{
  content: '▪';
  position: absolute;
  left: 0;
  color: var(--color-primary);
  font-size: 14px;
}}

/* Audit / Verification Table */
.table-wrap {{
  width: 100%;
  overflow-x: auto;
  border: 1px solid var(--color-rule);
  border-radius: 6px;
  background-color: var(--color-white);
}}

.audit-table {{
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-size: 14px;
}}

.audit-table th,
.audit-table td {{
  padding: 16px 20px;
  border-bottom: 1px solid var(--color-rule);
  vertical-align: top;
}}

.audit-table thead th {{
  background-color: var(--color-table-tint);
  color: var(--color-charcoal);
  font-size: 13px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 2px solid var(--color-primary);
}}

.audit-table tbody tr:nth-child(even) {{
  background-color: var(--color-table-row);
}}

.audit-table tbody tr:last-child th,
.audit-table tbody tr:last-child td {{
  border-bottom: none;
}}

.audit-component {{
  font-weight: 700;
  color: var(--color-charcoal);
}}

.audit-component strong {{
  display: block;
  font-size: 14.5px;
  margin-bottom: 4px;
}}

.audit-sub {{
  display: block;
  font-size: 12px;
  color: var(--color-muted);
  font-weight: 400;
  line-height: 1.35;
}}

.audit-cell-status {{
  display: inline-block;
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 3px 8px;
  border-radius: 3px;
  margin-bottom: 6px;
}}

.status-ok {{
  background-color: var(--color-valid-bg);
  color: var(--color-valid-text);
  border: 1px solid var(--color-valid-border);
}}

.status-warn {{
  background-color: var(--color-partial-bg);
  color: var(--color-partial-text);
  border: 1px solid var(--color-partial-border);
}}

.audit-table td p {{
  font-size: 13px;
  line-height: 1.45;
  color: var(--color-charcoal);
}}

.audit-table code {{
  font-family: var(--font-mono);
  font-size: 12px;
  background-color: #EAEAEA;
  padding: 1px 4px;
  border-radius: 3px;
}}

/* Limitations Matrix */
.limits-matrix {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}}

.limit-box {{
  background-color: var(--color-white);
  border: 1px solid var(--color-rule);
  border-left: 4px solid var(--color-primary);
  border-radius: 4px;
  padding: 24px;
}}

.limit-num {{
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 800;
  color: var(--color-primary);
  margin-bottom: 8px;
}}

.limit-title {{
  font-size: 17px;
  font-weight: 800;
  color: var(--color-charcoal);
  margin-bottom: 10px;
}}

.limit-text {{
  font-size: 14px;
  line-height: 1.55;
  color: var(--color-charcoal);
}}

.limit-text code {{
  font-family: var(--font-mono);
  font-size: 12.5px;
  background-color: #EAEAEA;
  padding: 1px 4px;
  border-radius: 3px;
}}

/* Final CTA Section */
.cta-section {{
  background-color: var(--color-surface-bg);
  border-bottom: 1px solid var(--color-rule);
}}

.cta-card {{
  background-color: var(--color-white);
  border: 2px solid var(--color-primary);
  border-radius: 8px;
  padding: 40px;
  display: grid;
  grid-template-columns: 1.3fr 0.7fr;
  gap: 36px;
  align-items: center;
}}

.cta-card-content {{
  display: flex;
  flex-direction: column;
  gap: 16px;
}}

.cta-eyebrow {{
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-primary);
}}

.cta-heading {{
  font-size: 26px;
  line-height: 1.3;
  font-weight: 800;
  color: var(--color-charcoal);
}}

.cta-sub {{
  font-size: 15px;
  line-height: 1.55;
  color: var(--color-muted);
}}

.cta-actions {{
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 8px;
  flex-wrap: wrap;
}}

.cta-meta {{
  background-color: var(--color-surface-bg);
  border: 1px solid var(--color-rule);
  border-radius: 6px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}}

.cta-meta-item {{
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13.5px;
  font-weight: 700;
  color: var(--color-charcoal);
}}

.meta-icon {{
  color: var(--color-primary);
  font-weight: 900;
  font-size: 15px;
}}

/* Footer */
.site-footer {{
  background-color: var(--color-white);
  padding-top: 48px;
  padding-bottom: 48px;
  border-top: 1px solid var(--color-rule);
}}

.footer-disclaimer-panel {{
  background-color: var(--color-surface-bg);
  border: 1px solid var(--color-rule);
  padding: 24px;
  border-radius: 6px;
  margin-bottom: 36px;
}}

.disclaimer-badge {{
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-primary);
  margin-bottom: 12px;
}}

.disclaimer-text {{
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--color-muted);
  margin-bottom: 10px;
}}

.disclaimer-text:last-child {{
  margin-bottom: 0;
}}

.disclaimer-text code {{
  font-family: var(--font-mono);
  font-size: 11.5px;
  background-color: #EAEAEA;
  padding: 1px 4px;
  border-radius: 3px;
}}

.footer-bottom {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  flex-wrap: wrap;
}}

.footer-brand-info {{
  display: flex;
  flex-direction: column;
  gap: 8px;
}}

.footer-logo {{
  display: block;
  height: 28px;
  width: auto;
}}

.footer-copyright {{
  font-size: 12px;
  color: var(--color-muted);
}}

.footer-links {{
  display: flex;
  align-items: center;
  gap: 20px;
  flex-wrap: wrap;
}}

.footer-links a {{
  font-size: 13px;
  color: var(--color-charcoal);
  text-decoration: none;
  font-weight: 700;
  transition: color 0.15s ease;
}}

.footer-links a:hover {{
  color: var(--color-primary);
  text-decoration: underline;
  text-underline-offset: 4px;
}}

/* Responsive Breakpoints */
@media (max-width: 960px) {{
  .hero-container {{
    grid-template-columns: 1fr;
    gap: 40px;
  }}
  .step-grid {{
    grid-template-columns: 1fr;
    gap: 16px;
  }}
  .limits-matrix {{
    grid-template-columns: 1fr;
  }}
  .cta-card {{
    grid-template-columns: 1fr;
    gap: 24px;
  }}
}}

@media (max-width: 680px) {{
  .site-nav {{
    display: none;
  }}
  .hero-title {{
    font-size: 28px;
  }}
  .hero-section {{
    padding-top: 32px;
    padding-bottom: 48px;
  }}
  .section-block {{
    padding-top: 48px;
    padding-bottom: 48px;
  }}
  .cta-card {{
    padding: 24px;
  }}
  .step-header {{
    padding: 14px 16px;
    gap: 12px;
  }}
  .step-body {{
    padding: 16px;
  }}
  .footer-bottom {{
    flex-direction: column;
    align-items: flex-start;
  }}
}}

/* Accessibility: Reduced Motion */
@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }}
}}
"""

    return f"""<!doctype html>
<html lang="id">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Sectoral — Riset Emiten Berbasis Bukti Cache Terverifikasi</title>
  <meta name="description" content="Sektoral mengubah data cache lokal Sectors menjadi company update emiten BEI dengan sitasi terverifikasi deterministik dan batasan bukti yang transparan.">
  <style>{css_styles}</style>
</head>
<body>
<!--
THESIS: Evidence-backed company research, not a generic AI finance landing page; refuse claims of live data or trading.
OWN-WORLD: Sectoral blue/white/charcoal/Roboto; thin rules, precise report-like diagrams, restrained teal and green accents.
STORY: Show how cached source rows become an evidence-checked company update, and what happens when evidence is incomplete.
FIRST VIEWPORT: Brand/navigation; headline and CTA left; labeled evidence-flow product preview right; cache-only note adjacent.
FORM: Evidence instrument, assigned structure, seed ae210778.
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
-->
  <a href="#konten-utama" class="skip-link">Lewati ke konten utama</a>

  <header class="site-header">
    <div class="header-container">
      <a href="/" class="brand-link" aria-label="Beranda Sectoral">
        <img src="/assets/brand/sectoral-logo.svg" alt="Sectoral" width="160" height="35" class="brand-logo">
      </a>
      <nav class="site-nav" aria-label="Navigasi Utama">
        <a href="#cara-kerja" class="nav-link">Cara kerja</a>
        <a href="#verifikasi" class="nav-link">Pemeriksaan bukti</a>
        <a href="#batasan" class="nav-link">Batasan & integritas</a>
        <a href="/research" class="nav-cta">Coba riset emiten</a>
      </nav>
    </div>
  </header>

  <main id="konten-utama">
    <!-- First Viewport / Evidence Instrument -->
    <section class="hero-section" aria-labelledby="hero-title">
      <div class="hero-container">
        <!-- Left Column: Core Value Proposition & Primary Action -->
        <div class="hero-content">
          <div class="kicker-badge">
            <span class="badge-indicator" aria-hidden="true"></span>
            <span class="kicker-text">Riset Emiten BEI · Berbasis Bukti Cache Terverifikasi</span>
          </div>

          <h1 id="hero-title" class="hero-title">
            Company update berbasis bukti, transparan pada batas data.
          </h1>

          <p class="hero-lead">
            Sektoral menghubungkan data fundamental emiten dari cache lokal Sectors menjadi laporan riset yang dapat diaudit. Setiap pernyataan dikaitkan dengan baris data aktual, dan validator deterministik memastikan sitasi sahih sebelum laporan terbit.
          </p>

          <div class="cta-group">
            <a href="/research" class="btn btn-primary">Coba riset emiten</a>
            <a href="#cara-kerja" class="btn btn-secondary">Cara kerja</a>
          </div>

          <!-- Adjacent Cache-Only & No-Advice Disclosure Box -->
          <aside class="disclosure-box" aria-label="Pengungkapan Operasional dan Batasan">
            <div class="disclosure-header">
              <span class="disclosure-tag">BATASAN SISTEM & LEGALITAS</span>
              <span class="disclosure-mode">Mode: Cache-Only</span>
            </div>
            <ul class="disclosure-list">
              <li><strong>Sumber Bertanggal:</strong> Harga pasar dibaca dari <code>data/sectors_cache.db</code>; pembangun PDF juga dapat memakai rilis resmi emiten yang disimpan lokal dengan tanggal dan halaman sumber.</li>
              <li><strong>Nalar AI, Bukan Data:</strong> LLM digunakan murni untuk penalaran dan penyusunan narasi, bukan sebagai generator angka harga atau estimasi pasar.</li>
              <li><strong>Gate Rilis:</strong> Draft menahan rating dan target harga sampai forecast serta valuasi sesuai profil emiten lolos pemeriksaan. Tidak ada eksekusi broker.</li>
            </ul>
          </aside>
        </div>

        <!-- Right Column: Evidence-flow Instrument Preview -->
        <div class="hero-instrument">
          <div class="instrument-panel">
            <div class="instrument-bar">
              <div class="instrument-title-group">
                <span class="instrument-dot" aria-hidden="true"></span>
                <span class="instrument-heading">Instrumen Alur Riset & Jejak Audit</span>
              </div>
              <span class="instrument-status-tag">Alur Ilustratif · Cache Lokal</span>
            </div>

            <figure class="flow-figure">
              <img src="/assets/brand/research-flow.svg" alt="Diagram alur kerja pembacaan cache, penalaran agen, dan validasi sitasi Sektoral" class="flow-preview-img" width="560" height="320">
              <figcaption class="flow-caption">
                Representasi alur data analitis lokal dari pembacaan database cache hingga validasi sitasi laporan.
              </figcaption>
            </figure>

            <div class="instrument-metrics">
              <div class="metric-row">
                <span class="metric-label">Sumber Data Pasar</span>
                <span class="metric-value"><code>data/sectors_cache.db</code></span>
              </div>
              <div class="metric-row">
                <span class="metric-label">Validasi Sitasi</span>
                <span class="metric-value-valid">100% Deterministic Row Match</span>
              </div>
              <div class="metric-row">
                <span class="metric-label">Penanganan Bukti Kurang</span>
                <span class="metric-value-partial">Explicit Partial / Draft (Tanpa Halusinasi)</span>
              </div>
              <div class="metric-row">
                <span class="metric-label">Koneksi Broker / Transaksi</span>
                <span class="metric-value">None (Hanya Informasi Riset)</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Scroll Section 1: Workflow Explanation (Cara Kerja) -->
    <section id="cara-kerja" class="section-block section-bordered" aria-labelledby="workflow-title">
      <div class="container">
        <div class="section-intro">
          <span class="section-kicker">METODOLOGI DETERMINISTIK</span>
          <h2 id="workflow-title" class="section-heading">Tiga Tahap Alur Riset Terikat Bukti</h2>
          <p class="section-desc">
            Sektoral meniadakan kesimpulan tanpa dasar. Setiap tahap dalam rantai analisis dirancang untuk memastikan bahwa setiap fakta dapat ditelusuri kembali ke baris data aslinya.
          </p>
        </div>

        <div class="interactive-steps" role="region" aria-label="Tahapan Pemeriksaan Bukti">
          <!-- Step 1 -->
          <details class="step-card" open>
            <summary class="step-header">
              <div class="step-badge">Tahap 01</div>
              <div class="step-header-text">
                <h3 class="step-title">Pembacaan Terarah dari Cache Lokal Sectors</h3>
                <p class="step-summary">Agen hanya mengakses endpoint cache yang tersedia untuk emiten terkait di dalam database SQLite lokal.</p>
              </div>
              <span class="step-toggle-icon" aria-hidden="true"></span>
            </summary>
            <div class="step-body">
              <div class="step-grid">
                <div class="step-detail-col">
                  <h4 class="step-subheading">Mekanisme Kerja</h4>
                  <p>Host mengeksekusi query data lokal ke <code>data/sectors_cache.db</code> (seperti ringkasan perusahaan, laporan keuangan terformat, rasio valuasi historis, dan ringkasan berita). Agen tidak memiliki akses jaringan ke API publik selama pembacaan.</p>
                </div>
                <div class="step-detail-col">
                  <h4 class="step-subheading">Jaminan Integritas</h4>
                  <ul class="step-list">
                    <li>Setiap baris yang dibaca dicatat secara deterministik ke dalam berkas jejak audit (<code>trace.json</code>).</li>
                    <li>Tidak ada injeksi data dari mesin pencari web, memori liar model, atau asumsi analis yang tidak tercatat.</li>
                  </ul>
                </div>
              </div>
            </div>
          </details>

          <!-- Step 2 -->
          <details class="step-card" open>
            <summary class="step-header">
              <div class="step-badge">Tahap 02</div>
              <div class="step-header-text">
                <h3 class="step-title">Penalaran Agen & Penyusunan Ringkasan Terikat Bukti</h3>
                <p class="step-summary">LLM memproses baris data terstruktur untuk menyusun observasi, implikasi, dan matriks valuasi.</p>
              </div>
              <span class="step-toggle-icon" aria-hidden="true"></span>
            </summary>
            <div class="step-body">
              <div class="step-grid">
                <div class="step-detail-col">
                  <h4 class="step-subheading">Mekanisme Kerja</h4>
                  <p>Model bahasa bertindak sebagai mesin nalar analitis (reasoning engine). Agen merumuskan company update dengan menyematkan sitasi terstruktur—mencakup nama endpoint, path kolom, dan nilai spesifik yang diambil.</p>
                </div>
                <div class="step-detail-col">
                  <h4 class="step-subheading">Jaminan Integritas</h4>
                  <ul class="step-list">
                    <li>Data angka tidak dihasilkan secara sintetis atau ditebak oleh model.</li>
                    <li>Jika metrik tertentu tidak tersedia pada cache emiten, agen wajib mencatat ketiadaan data tersebut.</li>
                  </ul>
                </div>
              </div>
            </div>
          </details>

          <!-- Step 3 -->
          <details class="step-card" open>
            <summary class="step-header">
              <div class="step-badge">Tahap 03</div>
              <div class="step-header-text">
                <h3 class="step-title">Validasi Sitasi Deterministik & Deteksi Parsial</h3>
                <p class="step-summary">Gatekeeper kode Python memverifikasi setiap klaim terhadap baris cache yang telah dibaca host.</p>
              </div>
              <span class="step-toggle-icon" aria-hidden="true"></span>
            </summary>
            <div class="step-body">
              <div class="step-grid">
                <div class="step-detail-col">
                  <h4 class="step-subheading">Mekanisme Kerja</h4>
                  <p>Validator non-LLM memeriksa setiap referensi dalam brief riset. Apakah endpoint benar-benar dibuka? Apakah nilai yang dikutip cocok dengan baris database? Jika seluruh sitasi valid, laporan final siap disusun.</p>
                </div>
                <div class="step-detail-col">
                  <h4 class="step-subheading">Jaminan Integritas</h4>
                  <ul class="step-list">
                    <li>Sitasi yang tidak valid atau bukti yang tidak memadai secara otomatis mengubah status hasil menjadi <strong>Parsial (Draft)</strong>.</li>
                    <li>Laporan yang berstatus parsial menampilkan banner pengungkapan eksplisit di bagian atas dokumen.</li>
                  </ul>
                </div>
              </div>
            </div>
          </details>
        </div>
      </div>
    </section>

    <!-- Scroll Section 2: What the Agent Checks (Verifikasi) -->
    <section id="verifikasi" class="section-block" aria-labelledby="verification-title">
      <div class="container">
        <div class="section-intro">
          <span class="section-kicker">TRANSPARANSI AUDIT</span>
          <h2 id="verification-title" class="section-heading">Apa yang Diperiksa oleh Validator Deterministik?</h2>
          <p class="section-desc">
            Sistem pengujian berbasis kode memastikan bahwa tidak ada klaim laporan yang lolos tanpa rujukan database yang sahih.
          </p>
        </div>

        <div class="table-wrap" role="region" aria-label="Tabel Perbandingan Verifikasi Bukti" tabindex="0">
          <table class="audit-table">
            <thead>
              <tr>
                <th scope="col" style="width: 26%;">Komponen Pemeriksaan</th>
                <th scope="col" style="width: 37%;">Kondisi Bukti Lengkap (Complete)</th>
                <th scope="col" style="width: 37%;">Kondisi Bukti Kurang / Gagal (Partial)</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <th scope="row" class="audit-component">
                  <strong>Pencocokan Sitasi Kuantitatif</strong>
                  <span class="audit-sub">Angka pendapatan, margin, valuasi, rasio utang</span>
                </th>
                <td>
                  <div class="audit-cell-status status-ok">Cocok 100%</div>
                  <p>Setiap angka cocok tepat dengan baris dan kolom yang dibaca dari <code>sectors_cache.db</code>.</p>
                </td>
                <td>
                  <div class="audit-cell-status status-warn">Ditolak / Ditandai</div>
                  <p>Angka yang tidak terverifikasi ditolak; bagian analisis dinyatakan tidak memiliki dukungan data.</p>
                </td>
              </tr>
              <tr>
                <th scope="row" class="audit-component">
                  <strong>Jejak Pembacaan Endpoint</strong>
                  <span class="audit-sub">Verifikasi rute data cache yang diakses</span>
                </th>
                <td>
                  <div class="audit-cell-status status-ok">Terverifikasi di Trace</div>
                  <p>Seluruh endpoint yang disitasi tercatat dalam log pembacaan host pada <code>trace.json</code>.</p>
                </td>
                <td>
                  <div class="audit-cell-status status-warn">Inkonsistensi Dicatat</div>
                  <p>Jika endpoint tidak dibaca atau kosong, validator melarang penyimpulan narasi.</p>
                </td>
              </tr>
              <tr>
                <th scope="row" class="audit-component">
                  <strong>Status Publikasi Dokumen</strong>
                  <span class="audit-sub">Penentuan tingkat kepercayaan laporan</span>
                </th>
                <td>
                  <div class="audit-cell-status status-ok">Laporan Terverifikasi</div>
                  <p>Company update diterbitkan dengan stempel kelayakan penuh dan siap ditinjau.</p>
                </td>
                <td>
                  <div class="audit-cell-status status-warn">Banner Parsial / Draft</div>
                  <p>Dokumen diberi label mencolok: <em>Analisis Parsial — Bukti Belum Lengkap</em>.</p>
                </td>
              </tr>
              <tr>
                <th scope="row" class="audit-component">
                  <strong>Perilaku Model Sintesis</strong>
                  <span class="audit-sub">Penanganan kekosongan informasi</span>
                </th>
                <td>
                  <div class="audit-cell-status status-ok">Sintesis Terbatas Sumber</div>
                  <p>Analisis dirumuskan murni dari perbandingan data historis yang tersedia.</p>
                </td>
                <td>
                  <div class="audit-cell-status status-warn">Tanpa Asumsi / Halusinasi</div>
                  <p>Sistem menolak mengisi celah data dengan tebakan generatif atau scraping luar.</p>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- Scroll Section 3: Source and Evidence Limitations (Batasan) -->
    <section id="batasan" class="section-block section-bordered" aria-labelledby="limits-title">
      <div class="container">
        <div class="section-intro">
          <span class="section-kicker">INTEGRITAS & BATASAN OPERASIONAL</span>
          <h2 id="limits-title" class="section-heading">Batasan yang Kami Pegang Teguh</h2>
          <p class="section-desc">
            Kepercayaan analisis lahir dari kejelasan mengenai apa yang bisa dan apa yang tidak bisa dilakukan oleh sistem.
          </p>
        </div>

        <div class="limits-matrix">
          <div class="limit-box">
            <div class="limit-num">01</div>
            <h3 class="limit-title">Penyimpanan Terisolasi (Cache-Only)</h3>
            <p class="limit-text">
              Siklus agen riset membaca snapshot cache lokal tanpa panggilan data pasar langsung. Pembangun PDF dapat menambahkan angka aktual dari rilis resmi emiten yang disimpan lokal dan diberi tanggal publikasi agar hasil dapat diaudit ulang.
            </p>
          </div>

          <div class="limit-box">
            <div class="limit-num">02</div>
            <h3 class="limit-title">Pemisahan Nalar dan Data Pasar</h3>
            <p class="limit-text">
              Model bahasa (LLM) difungsikan khusus sebagai mesin sintesis nalar, bukan repositori data pasar. Angka finansial, rasio valuasi, dan tanggal laporan selalu diambil langsung dari database terstruktur, menghilangkan risiko fabrikasi angka.
            </p>
          </div>

          <div class="limit-box">
            <div class="limit-num">03</div>
            <h3 class="limit-title">Tanpa Integrasi Broker & Transaksi</h3>
            <p class="limit-text">
              Sektoral adalah peranti riset analitis murni. Platform tidak terhubung ke rekening efek nasabah, broker pasar modal, atau gateway eksekusi perdagangan. Kami tidak memfasilitasi penempatan pesanan beli atau jual dalam bentuk apa pun.
            </p>
          </div>

          <div class="limit-box">
            <div class="limit-num">04</div>
            <h3 class="limit-title">Bukan Rekomendasi Investasi</h3>
            <p class="limit-text">
              Keluaran riset menyajikan skenario analitis dan komparasi fundamental untuk mendukung kerja analis, bukan merupakan ajakan membeli efek, menetapkan target harga spekulatif, atau memberi advis finansial terlisensi.
            </p>
          </div>
        </div>
      </div>
    </section>

    <!-- Scroll Section 4: Final CTA -->
    <section class="section-block cta-section" aria-labelledby="final-cta-title">
      <div class="container">
        <div class="cta-card">
          <div class="cta-card-content">
            <span class="cta-eyebrow">UJI COBA WORKFLOW LOKAL</span>
            <h2 id="final-cta-title" class="cta-heading">Mulai susun company update dengan bukti terverifikasi.</h2>
            <p class="cta-sub">
              Jalankan agen riset untuk emiten pilihan Anda, amati pembacaan cache secara langsung, dan periksa jejak sitasi laporan lengkap dengan batasan buktinya.
            </p>
            <div class="cta-actions">
              <a href="/research" class="btn btn-primary btn-large">Coba riset emiten</a>
              <a href="#cara-kerja" class="btn btn-secondary">Pelajari alur kerja</a>
            </div>
          </div>
          <div class="cta-meta">
            <div class="cta-meta-item">
              <span class="meta-icon" aria-hidden="true">✓</span>
              <span>Validasi sitasi deterministik</span>
            </div>
            <div class="cta-meta-item">
              <span class="meta-icon" aria-hidden="true">✓</span>
              <span>Jejak audit trace transparan</span>
            </div>
            <div class="cta-meta-item">
              <span class="meta-icon" aria-hidden="true">✓</span>
              <span>Penanganan parsial tanpa halusinasi</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  </main>

  <!-- Site Footer -->
  <footer class="site-footer">
    <div class="container">
      <div class="footer-disclaimer-panel" role="note" aria-label="Pernyataan Pengungkapan dan Sanggahan Resmi">
        <div class="disclaimer-badge">PENGUNGKAPAN PENTING & BATASAN TANGGUNG JAWAB</div>
        <p class="disclaimer-text">
          <strong>CATATAN RISET:</strong> Sektoral mengolah harga dari Sectors (<code>data/sectors_cache.db</code>) dan, untuk PDF tertentu, rilis resmi emiten yang disimpan lokal. Draft tidak memuat rating atau target harga; keluaran produksi hanya dapat memuatnya setelah pemeriksaan data, forecast, dan valuasi lolos. Keputusan investasi tetap tanggung jawab pembaca.
        </p>
        <p class="disclaimer-text">
          Keputusan investasi sepenuhnya merupakan tanggung jawab mandiri pembaca dan investor. Selalu lakukan uji tuntas (due diligence) independen dan konsultasikan dengan penasihat keuangan berlisensi sebelum mengambil keputusan investasi. Sektoral tidak terhubung dengan broker dan tidak mengeksekusi pesanan efek.
        </p>
      </div>

      <div class="footer-bottom">
        <div class="footer-brand-info">
          <img src="/assets/brand/sectoral-logo.svg" alt="Sectoral" width="130" height="29" class="footer-logo">
          <p class="footer-copyright">
            © 2026 Sektoral. Dibangun untuk Track AI Agents & Assistants — Sectors Hackathon 2026.
          </p>
        </div>
        <div class="footer-links">
          <a href="/research">Aplikasi Riset</a>
          <a href="#cara-kerja">Cara Kerja</a>
          <a href="#verifikasi">Pemeriksaan Bukti</a>
          <a href="#batasan">Batasan Sistem</a>
        </div>
      </div>
    </div>
  </footer>
</body>
</html>"""
