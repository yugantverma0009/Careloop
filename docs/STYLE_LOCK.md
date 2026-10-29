# CareLoop Design System & Style Lock

> **MANDATORY STYLE LOCK:** No new UI libraries, fonts, colors, or icon sets. All new screens and upgraded views must be composed strictly of the existing design tokens and patterns documented here. Landing, login, and staff pages must remain visually identical (visual regression threshold: <0.1% pixel change).

---

## 1. Design Tokens (from `frontend/src/index.css`)

### 1.1 Typography
- **Primary Sans Font (`--font-sans`):** `'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`
  - Body copy: `13px` / `14px` (upgrade requirement: patient body minimum `16px` for accessibility, using same font family)
  - Section headers: `16px` / `18px`, Weight: `800`
  - Page titles: `26px`, Weight: `800`, Letter-spacing: `-0.025em`
  - Supertitles / Category labels: `10px` / `11px`, Weight: `800`, Letter-spacing: `0.06em`, Text-transform: `uppercase`
- **Monospace Font (`--font-mono`):** `'JetBrains Mono', monospace`
  - Used for: telemetry digits, timestamps, code snippets, pill counters

### 1.2 Color Palette (CSS Custom Properties)

| Token Name | Light Theme (`[data-theme="light"]`) | Dark Theme (`[data-theme="dark"]`) | Usage / Semantics |
|---|---|---|---|
| `--bg-base` | `#f8fafc` (slate-50) | `#0b111e` (deep navy) | Application page background |
| `--bg-surface` | `#ffffff` | `#111a2c` | Main card surfaces, top navigation bar |
| `--bg-card` | `#ffffff` | `#152238` | Container card surfaces |
| `--bg-card-hover` | `#f1f5f9` | `#1b2a45` | Hover state on rows / interactive surfaces |
| `--bg-input` | `#ffffff` | `#0e1726` | Input fields, textareas |
| `--border-subtle` | `#e2e8f0` | `#1e2e4a` | Card borders, dividers, subtle row lines |
| `--border-strong` | `#cbd5e1` | `#2a3f63` | Input field borders, button outlines |
| `--text-primary` | `#0f172a` (slate-900) | `#f8fafc` (slate-50) | High-contrast headings and body text |
| `--text-secondary` | `#475569` (slate-600) | `#cbd5e1` (slate-300) | Secondary descriptions, subheadings |
| `--text-muted` | `#64748b` (slate-500) | `#8497b0` | Helper text, small timestamps, badges |
| `--accent-teal` | `#0d9488` | `#14b8a6` | Primary brand accent, progress, toggles |
| `--accent-teal-hover` | `#0f766e` | `#2dd4bf` | Teal button hover |
| `--accent-teal-soft` | `#ecfdf5` | `rgba(20, 184, 166, 0.15)` | Teal pill / card accent background |
| `--accent-teal-text` | `#065f46` | `#5eead4` | Text inside teal pill |
| `--accent-blue` | `#0284c7` | `#38bdf8` | Interactive active nav links, focus rings |
| `--accent-blue-hover` | `#0369a1` | `#0284c7` | Blue button hover |
| `--accent-blue-soft` | `#eff6ff` | `rgba(56, 189, 248, 0.15)` | Active tab background, blue pill background |
| `--accent-blue-text` | `#1d4ed8` | `#7dd3fc` | Text inside blue pill |
| `--alert-red` | `#dc2626` | `#f87171` | Emergency banner, urgent alert state |
| `--alert-red-soft` | `#fef2f2` | `rgba(248, 113, 113, 0.15)` | Alert banner background |
| `--alert-red-text` | `#991b1b` | `#fca5a5` | Text inside red banner |
| `--warning-amber` | `#d97706` | `#fbbf24` | Missed/unconfirmed warning pill, due now |
| `--warning-amber-soft` | `#fffbeb` | `rgba(251, 191, 36, 0.15)` | Amber pill / banner background |
| `--warning-amber-text` | `#92400e` | `#fde68a` | Text inside amber pill |
| `--success-green` | `#059669` | `#34d399` | Taken pill dot, success confirmation |
| `--success-green-soft` | `#f0fdf4` | `rgba(52, 211, 153, 0.15)` | Green pill background |
| `--success-green-text` | `#166534` | `#a7f3d0` | Text inside green pill |
| `--header-bg` | `#ffffff` | `#111a2c` | Top header bar background |
| `--header-border` | `#e2e8f0` | `#1e2e4a` | Top header divider |
| `--sidebar-bg` | `#ffffff` | `#0f1828` | Left navigation sidebar background |
| `--sidebar-border` | `#e2e8f0` | `#1e2e4a` | Left sidebar border |

### 1.3 Elevation & Shadows
- `--shadow-subtle`: `0 1px 3px 0 rgba(0, 0, 0, 0.05), 0 1px 2px -1px rgba(0, 0, 0, 0.05)` (Light) / `0 1px 3px rgba(0, 0, 0, 0.3)` (Dark)
- `--shadow-card`: `0 4px 6px -1px rgba(15, 23, 42, 0.04), 0 2px 4px -2px rgba(15, 23, 42, 0.03)` (Light) / `0 4px 12px rgba(0, 0, 0, 0.35)` (Dark)
- `--shadow-float`: `0 10px 25px -3px rgba(15, 23, 42, 0.08), 0 4px 6px -4px rgba(15, 23, 42, 0.03)` (Light) / `0 10px 30px rgba(0, 0, 0, 0.5)` (Dark)

### 1.4 Border Radii
- Standard Card: `12px`
- Action Button / Input: `8px`
- Small Badge / Action Chip: `6px` / `8px`
- Status Pill: `14px` (fully rounded capsule)
- Circle Avatar / Dot: `50%`

---

## 2. Existing Component Catalog

### 2.1 Navigation Sidebar (240px fixed)
- Background: `var(--sidebar-bg)`
- Border Right: `1px solid var(--sidebar-border)`
- Brand Header: `IconLogo` (34px) + "CareLoop" (`#0d9488` highlight) + "Recovery portal" subtitle
- Category Labels: `10px`, weight `800`, uppercase, `#94a3b8`, tracking `0.06em`
- Nav Item Button:
  - Default: transparent background, `var(--text-secondary)`, `13px`, font-weight `500`
  - Active: `#eff6ff` (light) / `rgba(56, 189, 248, 0.15)` (dark), text `#0284c7`, font-weight `700`
  - Badge: Capsule `11px`, bold, `#e2e8f0` (default) or `#0284c7` / `#ffffff` (active)

### 2.2 Top Header Bar (64px fixed)
- Background: `var(--header-bg)`
- Border Bottom: `1px solid var(--header-border)`
- Breadcrumb Title: "CARELOOP" (`10px`, bold) + Section Title (`13px`, bold)
- Centered Search Box: `360px` width, background `var(--bg-base)`, border `1px solid var(--border-strong)`, rounded `8px`, with `Ctrl+K` chip
- Controls (Right):
  - Language Toggle: segmented pill (`EN` | `HI`), active state background `#0d9488`, text `#ffffff`
  - Role Switcher (`SwitchDemoWorkspace`): compact dropdown button
  - User Avatar: `32px` circular avatar (`#0f172a`), patient initials + name and discharge day badge

### 2.3 Cards & Containers
- Standard Card Container:
  - Background: `var(--bg-surface)`
  - Border: `1px solid var(--border-subtle)`
  - Border Radius: `12px`
  - Box Shadow: `var(--shadow-card)`
  - Padding: `20px 22px` or `22px 24px`

### 2.4 Stat KPI Cards (4-column grid)
- Dimensions: Equal 4-column responsive grid (`repeat(4, 1fr)`, gap `18px`)
- Layout:
  - Top Right: `36x36px` icon box (rounded `10px`, light background + subtle border, colored stroke)
  - Label: `12px`, `var(--text-muted)`, font-weight `600`
  - Metric Value: `28px`, font-weight `800`, `var(--text-primary)`, monospace font for readings
  - Sub-indicator: `11px`, `var(--text-muted)` or status pill

### 2.5 Status Pills (`.status-pill`)
- Base: `display: inline-flex`, `align-items: center`, `gap: 6px`, `padding: 3px 10px`, `border-radius: 14px`, `font-size: 11px`, `font-weight: 600`
- Variants:
  - `.status-pill-green`: `var(--success-green-soft)` bg, `var(--success-green-text)` text, dot: `var(--success-green)`
  - `.status-pill-blue`: `var(--accent-blue-soft)` bg, `var(--accent-blue-text)` text, dot: `var(--accent-blue)`
  - `.status-pill-amber`: `var(--warning-amber-soft)` bg, `var(--warning-amber-text)` text, dot: `var(--warning-amber)`
  - `.status-pill-red`: `var(--alert-red-soft)` bg, `var(--alert-red-text)` text, dot: `var(--alert-red)`

### 2.6 Buttons
- **Primary Action Button:**
  - Background: `#0f172a` (light) / `#f8fafc` (dark, with dark text) or `#0d9488` (teal accent)
  - Color: `#ffffff` (light) / `#0f172a` (dark)
  - Border: none
  - Radius: `8px`
  - Font Size: `12px` / `13px`, weight `700`
  - Tap target: min height `40px` (extended to min `44px` for touch targets)
- **Secondary / Outline Button:**
  - Background: `var(--bg-surface)`
  - Border: `1px solid var(--border-strong)`
  - Color: `var(--text-primary)`
  - Radius: `8px`
  - Font Size: `12px`, weight `600`

### 2.7 Tables
- Header Row: border bottom `1px solid var(--border-subtle)`, headers `11px`, uppercase, bold, `#94a3b8`, padding `10px 12px`
- Table Body Rows: border bottom `1px solid var(--border-subtle)`, hover background `var(--bg-card-hover)`, padding `12px`

### 2.8 Alert Banners
- Red Alert Banner (Urgent/Emergency):
  - Background: `var(--alert-red-soft)`
  - Border: `1px solid var(--alert-red)`
  - Border Radius: `12px`
  - Icon: 36x36px `#dc2626` square with white `IconAlertTriangle`
  - Heading: `14px`, bold, `var(--alert-red-text)`
  - Subtitle: `13px`, `var(--alert-red-text)`

### 2.9 Icons (`frontend/src/components/Icons.jsx`)
Available native SVGs: `IconLogo`, `IconStethoscope`, `IconNurse`, `IconPatient`, `IconCaregiver`, `IconPill`, `IconHeartPulse`, `IconActivity`, `IconShieldCheck`, `IconAlertTriangle`, `IconBell`, `IconClock`, `IconCheck`, `IconChevronDown`, `IconChevronRight`, `IconSun`, `IconMoon`, `IconLogOut`, `IconLock`, `IconEye`, `IconEyeOff`, `IconSend`, `IconMessageSquare`, `IconFileText`, `IconSparkles`, `IconCalendar`, `IconUser`, `IconArrowRight`, `IconRefresh`, `IconSearch`.

---

## 3. New Components (Constructed ONLY from Existing Tokens)

To fulfill the requirements of the upgrade brief without introducing foreign UI libraries or style violations, the following components are explicitly constructed from the tokens above:

### 3.1 Month Calendar Grid (`My calendar` - Phase 2)
- **Container:** Standard card (`var(--bg-surface)`, border `1px solid var(--border-subtle)`, radius `12px`, padding `20px`)
- **Header:** Month & Year title (`16px`, weight `800`), Prev / Next buttons (`36x36px`, border `1px solid var(--border-strong)`, radius `8px`), Today button (Secondary button)
- **Grid Structure:** `display: grid`, `grid-template-columns: repeat(7, 1fr)`, gap `8px`
- **Day Headers (M, T, W, T, F, S, S):** `11px`, font-weight `700`, color `var(--text-muted)`, text-align center
- **Day Cell:**
  - Min height `72px`, radius `8px`, border `1px solid var(--border-subtle)`
  - Hover background: `var(--bg-card-hover)`
  - Current day highlight: border `2px solid var(--accent-blue)`
  - Day Number: `12px`, font-family `var(--font-mono)`, font-weight `700`, color `var(--text-primary)`
  - Markers Row: `display: flex`, `gap: 4px`, `justify-content: center`, `align-items: center`
    - Medicine marker: `6px` solid circle (`var(--success-green)` if all taken, `var(--warning-amber)` if pending/missed)
    - Appointment marker: `IconCalendar` (10x10px, `var(--accent-blue)`)
    - Check-in marker: `IconCheck` (10x10px, `var(--accent-teal)`)

### 3.2 Week Strip (Overview Widget - Phase 1/2)
- Compact 7-column bar embedded on the Overview page
- Each day shows Day Initial (M, T...), Day Number (24, 25...), and status dot (`6px` green/amber/grey)
- Tapping opens the day's drawer/sheet

### 3.3 Pain Scale Button Selector (Check-in - Phase 3)
- Replaces HTML range slider with 11 discrete, tappable number buttons (0 to 10)
- Button dimensions: minimum `44x44px` (satisfying WCAG AA touch targets)
- Radius: `8px`, font-family `var(--font-mono)`, font-weight `800`, font-size `16px`
- Color coding:
  - 0–3 (Mild): `var(--success-green-soft)` background, `var(--success-green-text)` text, border `1px solid var(--success-green)`
  - 4–6 (Moderate): `var(--warning-amber-soft)` background, `var(--warning-amber-text)` text, border `1px solid var(--warning-amber)`
  - 7–10 (Severe): `var(--alert-red-soft)` background, `var(--alert-red-text)` text, border `1px solid var(--alert-red)`
- Clear persistent labels: "No pain" at 0, "Moderate" at 5, "Worst pain" at 10

### 3.4 Symptom & Location Multi-Select Chips (Check-in - Phase 3)
- Chip: `display: inline-flex`, `padding: 8px 14px`, `border-radius: 8px`, `font-size: 13px`, `font-weight: 600`, `cursor: pointer`
- Unselected: background `var(--bg-base)`, border `1px solid var(--border-strong)`, color `var(--text-secondary)`
- Selected: background `var(--accent-blue-soft)`, border `1px solid var(--accent-blue)`, color `var(--accent-blue-text)`, font-weight `700`

### 3.5 Grounded RAG Citation & Source Drawer (Phase 4)
- **Source Chip:** In-line `.status-pill-blue` below assistant response (e.g. `Discharge summary · Follow-up · p.2`)
- **Inspection Drawer / Panel:**
  - Background `var(--bg-surface)`, border `1px solid var(--border-subtle)`, radius `12px`, padding `18px`, shadow `var(--shadow-float)`
  - Shows verified verbatim chunk text with highlighted matching sentences
  - Close button with `Esc` keyboard handler and backdrop overlay

---

## 4. Theme & Accessibility Invariants

1. **Dark Mode Integration:** Every component and inline style MUST use the CSS variables (`var(--bg-base)`, `var(--bg-surface)`, `var(--text-primary)`, `var(--border-subtle)`) instead of hardcoded hex values like `#ffffff` or `#0f172a`.
2. **Hindi (HI) Typography:** Hindi text length expansion (typically 10-25% wider) must not cause container clipping or horizontal scrolling. Relative flex layouts with `flex-wrap: wrap` are strictly applied.
3. **Contrast & Zoom:** Minimum contrast ratio 4.5:1 for standard text and 3:1 for large text/icons across both light and dark themes. Text sizes scale with user browser preferences (minimum 16px for patient body text).

---

## 5. Role Accent Colors & Visual Differentiation

Per Section 2.4 of the *Roles & Simplification Plan*, roles MUST differ visually without changing the core style tokens. Each role utilizes a dedicated accent color chosen from the existing palette:

| Role | User Persona | Accent Color | Hex Code | Soft / Light Background | Dark Mode Background | Semantic Purpose |
|---|---|---|---|---|---|---|
| **Doctor** | Dr. Ananya Sharma | **Purple** | `#7c3aed` | `#f5f3ff` | `rgba(124, 58, 237, 0.15)` | Clinical decision-making & governance authority |
| **Nurse** | Priya Nair | **Blue** | `#0284c7` | `#eff6ff` | `rgba(56, 189, 248, 0.15)` | Active call list & frontline care coordination |
| **Patient** | Aarav Patel | **Teal** | `#0d9488` | `#ecfdf5` | `rgba(20, 184, 166, 0.15)` | Personal recovery, medications & wellness |
| **Family Helper** | Neha Patel | **Amber** | `#d97706` | `#fffbeb` | `rgba(251, 191, 36, 0.15)` | Caregiver support & emergency contact |

### Role Visual Signatures:
- **Active Navigation Pill:** Uses the role's accent color for text and soft background.
- **Top Header Role Chip:** Compact capsule showing the role's icon and label tinted in the role's accent.
- **Page Supertitle / Kicker:** Uppercase tracker text in the role's accent color (e.g. `DOCTOR DESK`, `NURSE DESK`, `MY RECOVERY`, `FAMILY VIEW`).

---

## 6. Phase 1 Baseline Screenshots Catalog

Saved under `docs/screenshots/phase1_baseline/`:

1. **Landing Page:**
   - Light: `docs/screenshots/phase1_baseline/landing_light.png`
   - Dark: `docs/screenshots/phase1_baseline/landing_dark.png`
2. **Login Page:**
   - Light: `docs/screenshots/phase1_baseline/login_light.png`
   - Dark: `docs/screenshots/phase1_baseline/login_dark.png`
3. **Doctor First Screen (`Dr. Ananya Sharma`):**
   - Light: `docs/screenshots/phase1_baseline/doctor_first_screen_light.png`
   - Dark: `docs/screenshots/phase1_baseline/doctor_first_screen_dark.png`
4. **Nurse First Screen (`Priya Nair`):**
   - Light: `docs/screenshots/phase1_baseline/nurse_first_screen_light.png`
   - Dark: `docs/screenshots/phase1_baseline/nurse_first_screen_dark.png`
5. **Patient First Screen (`Aarav Patel`):**
   - Light: `docs/screenshots/phase1_baseline/patient_first_screen_light.png`
   - Dark: `docs/screenshots/phase1_baseline/patient_first_screen_dark.png`
6. **Family Helper First Screen (`Neha Patel`):**
   - Light: `docs/screenshots/phase1_baseline/family_first_screen_light.png`
   - Dark: `docs/screenshots/phase1_baseline/family_first_screen_dark.png`

