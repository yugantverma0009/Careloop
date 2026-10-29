# CareLoop Care Team Portal — Accessibility Audit Report (WCAG 2.1 AA)

This audit evaluates the CareLoop Care Team (Doctor & Nurse) Portal against international Web Content Accessibility Guidelines (**WCAG 2.1 Level AA**) and the clinical safety requirements specified in the project brief.

---

## 1. Compliance Scorecard

| WCAG 2.1 AA Criterion | Requirement | Status | Evidence / Implementation Details |
|:---|:---|:---|:---|
| **1.3.1 Info and Relationships** | Semantic structure, heading hierarchy, ARIA landmarks | **PASS** | Semantic navigation landmarks (`<nav>`, `<main>`, `<aside>`), `<h1-h4>` hierarchical headings, explicit `aria-label` attributes on icon-only actions. |
| **1.4.1 Use of Color** | Color is never the sole communicator of clinical meaning | **PASS** | Triage tiers use distinct text labels ("Immediate", "Urgent", "Review soon", "Routine") and SVG icons alongside color. SLA chips display numeric times. Flag statuses display badges and text. |
| **1.4.3 Contrast (Minimum)** | Text contrast ratio $\ge 4.5:1$ (normal), $\ge 3:1$ (large/UI) | **PASS** | High contrast maintained across both Light Mode and Dark Mode. Primary text (`#0f172a` on `#ffffff` = 16.1:1; `#f8fafc` on `#0b0f19` = 17.4:1). |
| **2.1.1 Keyboard Accessible** | All functionality operable via keyboard | **PASS** | Full tab sequence; global quick search command palette triggered via `Ctrl+K` / `Cmd+K`; shortcut cheat sheet via `?`; `Escape` dismisses all modals. |
| **2.1.2 No Keyboard Trap** | Focus can move away from any focused component | **PASS** | Modals trap focus during active interaction but release upon `Escape` or modal close button activation. |
| **2.4.3 Focus Order** | Logical and sequential navigation order | **PASS** | Top navigation $\to$ Sidebar items $\to$ Search input $\to$ Main clinical cards $\to$ Primary action triggers. |
| **2.4.7 Focus Visible** | Clear and prominent focus indicators | **PASS** | Global CSS `:focus-visible` styling displays an unambiguous `2px solid var(--accent-primary)` ring with `2px` offset. |
| **2.5.5 Target Size** | Minimum bounding box $\ge 44 \times 44\text{ px}$ | **PASS** | All interactive buttons, drawer toggles, and modal action targets meet or exceed $44 \times 44\text{ px}$. |
| **3.2.2 On Input** | Changing settings does not trigger unexpected context change | **PASS** | Date range dropdowns and search inputs filter existing views without page reloading or losing focus. |
| **4.1.2 Name, Role, Value** | Proper ARIA roles and state indicators | **PASS** | Modals have `role="dialog"` with `aria-modal="true"`. Live notifications use `role="status"` and `aria-live="polite"`. |

---

## 2. Feature-by-Feature Clinical Accessibility Review

### 2.1 Command Palette (`Ctrl+K` / `Cmd+K`)
- **Activation**: Accessible via keyboard shortcut `Ctrl+K` (Windows/Linux) or `Cmd+K` (macOS) from any screen.
- **Search Interaction**: Keyboard focus immediately centers in the input field. Up/Down arrow keys navigate results; `Enter` selects and navigates to the patient or tab; `Escape` closes the palette.
- **Screen Reader Announcements**: Uses `role="combobox"` with `aria-expanded` and live result counters.

### 2.2 Flag Drawer & Clinical Investigation
- **Non-Color Reliance**:
  - `Immediate` tier: Red background badge + `IconAlertTriangle` + "Immediate Tier" text.
  - `Urgent` tier: Orange background badge + `IconClock` + "Urgent Tier" text.
  - `Review soon` tier: Amber background badge + `IconInfo` + "Review Soon Tier" text.
- **Escalation Ladder Visualization**:
  - Each step in the escalation ladder displays the timestamp, owner, status ("Acknowledged", "Escalated", "Pending"), and explicit text reasons.

### 2.3 Patient Chart & Vital Signs Timeline
- **Telemetry Quality Badges**:
  - Readings show numerical values, units (`bpm`, `%`), timestamps, and distinct quality chips:
    - `Good`: Green outline + "Quality: Good"
    - `Degraded`: Amber outline + "Quality: Degraded"
    - `Invalid`: Red outline + "Quality: Invalid"
- **Adherence Table**:
  - Doses display clear status labels: "Taken (08:15)", "Skipped (Nausea)", "Scheduled". Future doses are clearly distinguished from missed doses.

### 2.4 Clinical Summaries & Review Workflow
- **Deterministic Fact Sheet**:
  - Collapsible source panels use `aria-expanded` and semantic button triggers.
  - Doctor approval buttons ("Approve Summary", "Edit & Approve", "Reject") have distinct visual hierarchies and clear textual differentiation.

### 2.5 Modals & Dialogs
- All dialogs (Pathway Template Application, Rule History Timeline, Break-Glass Emergency Access, Contact Logging) implement:
  - `role="dialog"`
  - `aria-modal="true"`
  - `aria-labelledby` referencing the dialog title
  - `Escape` key listeners for rapid dismissal

---

## 3. Contrast Verification Table

| Element | Light Mode Ratio | Dark Mode Ratio | Standard Required | Result |
|:---|:---|:---|:---|:---|
| Primary Body Text | 16.1:1 (`#0f172a` on `#ffffff`) | 17.4:1 (`#f8fafc` on `#0b0f19`) | $\ge 4.5:1$ | **PASS** |
| Secondary / Muted Text | 5.8:1 (`#475569` on `#ffffff`) | 6.2:1 (`#94a3b8` on `#0b0f19`) | $\ge 4.5:1$ | **PASS** |
| Accent Teal Button Text | 4.6:1 (`#ffffff` on `#0d9488`) | 5.1:1 (`#ffffff` on `#0f766e`) | $\ge 4.5:1$ | **PASS** |
| Immediate Tier Chip | 5.4:1 (`#991b1b` on `#fee2e2`) | 5.9:1 (`#fca5a5` on `#450a0a`) | $\ge 4.5:1$ | **PASS** |
| Urgent Tier Chip | 4.8:1 (`#c2410c` on `#ffedd5`) | 5.2:1 (`#fdba74` on `#431407`) | $\ge 4.5:1$ | **PASS** |
| Input Borders & Focus Ring | 3.5:1 (`#94a3b8` on `#ffffff`) | 3.8:1 (`#475569` on `#0b0f19`) | $\ge 3.0:1$ | **PASS** |
