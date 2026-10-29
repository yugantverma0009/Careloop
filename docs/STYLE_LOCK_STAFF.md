# CareLoop Care Team Portal — Visual Style Lock

This document locks the visual styling and UI component architecture for the **Care Team Portal (`/staff`)** in accordance with **Brief Section 1.3**.

> **MANDATORY STYLE LOCK RULE**:  
> No new CSS frameworks, UI component libraries, external font families, or ad-hoc color codes may be introduced. All screens and sub-components must be constructed strictly from the design tokens and component patterns documented here. Landing, Login, and Patient pages must remain visually identical (<0.1% pixel difference).

---

## 1. Design Tokens & Color Palette

The CareLoop design system uses the **BhoomiSetu Signature Clinical Palette** defined in `frontend/src/index.css`:

### 1.1 CSS Variables & Palette Tokens

| Token | Light Mode Value | Dark Mode Value | Usage / Semantic Role |
|---|---|---|---|
| `--navy-deep` | `#0b1528` | `#070d18` | Primary brand headers, dark accent surfaces |
| `--navy-darker` | `#070e1c` | `#040810` | Extreme deep backgrounds |
| `--bg-base` | `#f8fafc` | `#0b111e` | Main page canvas background |
| `--bg-surface` | `#ffffff` | `#111a2c` | Content containers, cards, tables, drawers |
| `--bg-card` | `#ffffff` | `#152238` | Stat cards, queue item cards |
| `--bg-card-hover`| `#f1f5f9` | `#1b2a45` | Hover state for table rows & card lists |
| `--bg-input` | `#ffffff` | `#0e1726` | Form inputs, select dropdowns, search boxes |
| `--border-subtle`| `#e2e8f0` | `#1e2e4a` | Card dividers, table borders, panel outlines |
| `--border-strong`| `#cbd5e1` | `#2a3f63` | Button outlines, active filter boundaries |
| `--text-primary` | `#0f172a` | `#f8fafc` | Primary typography, headers, patient names |
| `--text-secondary`| `#475569` | `#cbd5e1` | Subtitles, event reasons, descriptions |
| `--text-muted` | `#64748b` | `#8497b0` | Meta timestamps, IDs, table headers |
| `--accent-teal` | `#0d9488` | `#14b8a6` | Primary action highlights, logo dot, verified icons |
| `--accent-teal-soft`| `#ecfdf5` | `rgba(20, 184, 166, 0.15)` | Verified badge background, success pill soft |
| `--accent-blue` | `#0284c7` | `#38bdf8` | Routine flags, active tab indicator, links |
| `--accent-blue-soft`| `#eff6ff` | `rgba(56, 189, 248, 0.15)` | Active navigation background, info pill soft |
| `--alert-red` | `#dc2626` | `#f87171` | Immediate review, emergency flags, critical alerts |
| `--alert-red-soft` | `#fef2f2` | `rgba(248, 113, 113, 0.15)` | Critical alert banners, immediate pill soft |
| `--warning-amber`| `#d97706` | `#fbbf24` | Urgent review, missed doses, pending reviews |
| `--warning-amber-soft`| `#fffbeb` | `rgba(251, 191, 36, 0.15)` | Urgent review pill soft, caution banners |
| `--success-green`| `#059669` | `#34d399` | Taken doses, resolved items, approved summaries |
| `--success-green-soft`| `#f0fdf4` | `rgba(52, 211, 153, 0.15)` | Resolved badge background |
| `--sidebar-bg` | `#ffffff` | `#0f1828` | Left vertical navigation bar |
| `--sidebar-border`| `#e2e8f0` | `#1e2e4a` | Sidebar right border |

---

## 2. Typography, Radii & Elevation

### 2.1 Fonts & Sizes
- **Primary Font Family**: `'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`
- **Monospace Font Family**: `'JetBrains Mono', monospace` (used for timestamps, scores, codes, patient IDs)
- **Hierarchy**:
  - Page Titles / Headings: `18px – 20px`, `fontWeight: 800`, `letterSpacing: '-0.025em'`
  - Section Headers: `15px – 16px`, `fontWeight: 800`
  - Stat Card Metrics: `28px`, `fontWeight: 800`
  - Table Headers: `11px`, `fontWeight: 700`, uppercase, `color: #94a3b8` / `var(--text-muted)`
  - Body Text: `13px`, `fontWeight: 500 – 600`, `lineHeight: 1.5`
  - Meta / Badges / Timestamps: `11px – 12px`, `fontWeight: 500 – 700`

### 2.2 Border Radii
- Pill Badges: `14px` (`border-radius: 14px`)
- Buttons & Dropdowns: `8px` (`border-radius: 8px`)
- Small Badges & Input fields: `6px` (`border-radius: 6px`)
- Cards & Content Containers: `12px – 14px` (`border-radius: 12px`)

### 2.3 Shadows
- Subtle (`--shadow-subtle`): `0 1px 3px 0 rgba(0, 0, 0, 0.05)` (light), `0 1px 3px rgba(0,0,0,0.3)` (dark)
- Card (`--shadow-card`): `0 4px 6px -1px rgba(15, 23, 42, 0.04)` (light), `0 4px 12px rgba(0,0,0,0.35)` (dark)
- Floating Modal/Drawer (`--shadow-float`): `0 10px 25px -3px rgba(15, 23, 42, 0.08)` (light), `0 10px 30px rgba(0,0,0,0.5)` (dark)

---

## 3. Existing Component Inventory

### 3.1 Stat Metric Card
```jsx
<div style={{
  background: 'var(--bg-surface, #ffffff)',
  border: '1px solid var(--border-subtle, #e2e8f0)',
  borderRadius: '12px',
  padding: '20px 22px',
  position: 'relative',
  boxShadow: 'var(--shadow-card)',
}}>
  <div style={{ position: 'absolute', top: '18px', right: '18px', width: '36px', height: '36px', borderRadius: '10px', background: 'var(--alert-red-soft)', color: 'var(--alert-red)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
    <IconAlertTriangle width={18} height={18} />
  </div>
  <div style={{ fontSize: '12px', color: 'var(--text-muted, #64748b)', fontWeight: 600 }}>Immediate review</div>
  <div style={{ fontSize: '28px', fontWeight: 800, color: 'var(--alert-red, #dc2626)', margin: '6px 0 2px' }}>{count}</div>
  <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>Target: under 15 minutes</div>
</div>
```

### 3.2 Status & Severity Pills
Using the global `.status-pill` classes:
- **Immediate Review / Emergency**: `<span className="status-pill status-pill-red">Immediate</span>`
- **Urgent Review**: `<span className="status-pill status-pill-amber">Urgent</span>`
- **Review Soon / Routine**: `<span className="status-pill status-pill-blue">Review soon</span>`
- **Resolved / Done**: `<span className="status-pill status-pill-green">Resolved</span>`

### 3.3 Buttons
- **Primary Action (Dark)**:
  `background: '#0f172a'`, `color: '#ffffff'`, `padding: '7px 14px'`, `borderRadius: '8px'`, `fontWeight: 700`, `fontSize: '12px'` (in dark mode: `background: 'var(--accent-teal, #14b8a6)'`, `color: '#070d18'`).
- **Secondary / Outlined Action**:
  `background: 'transparent'`, `border: '1px solid var(--border-strong, #cbd5e1)'`, `color: 'var(--text-primary)'`, `borderRadius: '8px'`, `padding: '7px 14px'`.
- **Destructive / Dismiss Action**:
  `background: 'transparent'`, `border: '1px solid var(--alert-red)'`, `color: 'var(--alert-red)'`.

### 3.4 Table Rows
- `borderBottom: '1px solid var(--border-subtle, #f1f5f9)'`
- `onMouseEnter`: `background: 'var(--bg-card-hover, #f8fafc)'`
- Padding: `12px 14px`

### 3.5 Sidebar Navigation Item with Count Badge
- Container: `padding: '9px 12px'`, `borderRadius: '8px'`, `fontWeight: 700 / 500`, `fontSize: '13px'`
- Active state: `background: 'var(--accent-blue-soft, #eff6ff)'`, `color: 'var(--accent-blue, #0284c7)'`
- Inactive state: `background: 'transparent'`, `color: 'var(--text-secondary, #475569)'`
- Count Badge: `fontSize: '11px'`, `fontWeight: 800'`, `padding: '2px 7px'`, `borderRadius: '10px'`, `background: '#e2e8f0'`

---

## 4. New Components Built Strictly From Existing Tokens

The following components are required for the upgrade and will be constructed purely from the tokens above:

1. **Patient Identity Header & Badge (`PatientIdentity`)**:
   Two identifiers shown everywhere: Full Name + Age + Patient Code (`CL-00001`) + Condition.
2. **Flag Detail Drawer (`FlagDrawer`)**:
   Slide-in modal panel (`maxWidth: 640px`) using `--bg-surface`, `--shadow-float`, with backdrop blur and Esc key dismissal.
3. **Task Queue Row with SLA Chip**:
   Task title + PatientIdentity + Due date + Overdue chip (`status-pill-red` with overdue hours).
4. **Timeline Readings Chart with Quality Markers**:
   SVG line chart of Heart Rate & SpO₂ with quality badges (Good/Simulated/Invalid) and dashed lines for clinician-approved thresholds.
5. **Shift Handoff Sheet (I-PASS Format)**:
   Sectioned layout (Illness severity, Patient summary, Action list, Situation awareness, Synthesis by receiver) using `--bg-card` and standard borders.
