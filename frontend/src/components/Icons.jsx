import React from 'react';

// Common SVG props
const defaultProps = {
  width: 18,
  height: 18,
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
};

export function IconStethoscope(props) {
  return (
    <svg {...defaultProps} {...props}>
      <path d="M4.5 3v5a4.5 4.5 0 0 0 9 0V3" />
      <path d="M4.5 3H2" />
      <path d="M13.5 3H16" />
      <path d="M9 12.5v3.5a4.5 4.5 0 0 0 9 0V11" />
      <circle cx="18" cy="10" r="2" />
    </svg>
  );
}

export function IconNurse(props) {
  return (
    <svg {...defaultProps} {...props}>
      <path d="M12 2a4 4 0 0 1 4 4v1H8V6a4 4 0 0 1 4-4z" />
      <path d="M16 7h4a2 2 0 0 1 2 2v2a8 8 0 0 1-8 8 8 8 0 0 1-8-8V9a2 2 0 0 1 2-2h4" />
      <line x1="12" y1="11" x2="12" y2="15" />
      <line x1="10" y1="13" x2="14" y2="13" />
    </svg>
  );
}

export function IconPatient(props) {
  return (
    <svg {...defaultProps} {...props}>
      <circle cx="12" cy="7" r="4" />
      <path d="M5.5 21a8.38 8.38 0 0 1 13 0" />
      <path d="M18 11l2 2 4-4" />
    </svg>
  );
}

export function IconCaregiver(props) {
  return (
    <svg {...defaultProps} {...props}>
      <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
    </svg>
  );
}

export function IconPill(props) {
  return (
    <svg {...defaultProps} {...props}>
      <path d="m10.5 20.5 10-10a4.95 4.95 0 1 0-7-7l-10 10a4.95 4.95 0 1 0 7 7Z" />
      <path d="m8.5 8.5 7 7" />
    </svg>
  );
}

export function IconHeartPulse(props) {
  return (
    <svg {...defaultProps} {...props}>
      <path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z" />
      <path d="M3.22 12H9.5l.5-1 2 4.5 2-7 1.5 3.5h5.27" />
    </svg>
  );
}

export function IconActivity(props) {
  return (
    <svg {...defaultProps} {...props}>
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
    </svg>
  );
}

export function IconShieldCheck(props) {
  return (
    <svg {...defaultProps} {...props}>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <polyline points="9 12 11 14 15 10" />
    </svg>
  );
}

export function IconAlertTriangle(props) {
  return (
    <svg {...defaultProps} {...props}>
      <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

export function IconBell(props) {
  return (
    <svg {...defaultProps} {...props}>
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  );
}

export function IconClock(props) {
  return (
    <svg {...defaultProps} {...props}>
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}

export function IconCheck(props) {
  return (
    <svg {...defaultProps} {...props}>
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

export function IconChevronDown(props) {
  return (
    <svg {...defaultProps} {...props}>
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}

export function IconChevronRight(props) {
  return (
    <svg {...defaultProps} {...props}>
      <polyline points="9 18 15 12 9 6" />
    </svg>
  );
}

export function IconSun(props) {
  return (
    <svg {...defaultProps} {...props}>
      <circle cx="12" cy="12" r="5" />
      <line x1="12" y1="1" x2="12" y2="3" />
      <line x1="12" y1="21" x2="12" y2="23" />
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
      <line x1="1" y1="12" x2="3" y2="12" />
      <line x1="21" y1="12" x2="23" y2="12" />
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
      <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
    </svg>
  );
}

export function IconMoon(props) {
  return (
    <svg {...defaultProps} {...props}>
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  );
}

export function IconLogOut(props) {
  return (
    <svg {...defaultProps} {...props}>
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" y1="12" x2="9" y2="12" />
    </svg>
  );
}

export function IconLock(props) {
  return (
    <svg {...defaultProps} {...props}>
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  );
}

export function IconEye(props) {
  return (
    <svg {...defaultProps} {...props}>
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

export function IconEyeOff(props) {
  return (
    <svg {...defaultProps} {...props}>
      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
      <line x1="1" y1="1" x2="23" y2="23" />
    </svg>
  );
}

export function IconSend(props) {
  return (
    <svg {...defaultProps} {...props}>
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  );
}

export function IconMessageSquare(props) {
  return (
    <svg {...defaultProps} {...props}>
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  );
}

export function IconFileText(props) {
  return (
    <svg {...defaultProps} {...props}>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <polyline points="10 9 9 9 8 9" />
    </svg>
  );
}

export function IconSparkles(props) {
  return (
    <svg {...defaultProps} {...props}>
      <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z" />
    </svg>
  );
}

export function IconCalendar(props) {
  return (
    <svg {...defaultProps} {...props}>
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
    </svg>
  );
}

export function IconUser(props) {
  return (
    <svg {...defaultProps} {...props}>
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  );
}

export function IconArrowRight(props) {
  return (
    <svg {...defaultProps} {...props}>
      <line x1="5" y1="12" x2="19" y2="12" />
      <polyline points="12 5 19 12 12 19" />
    </svg>
  );
}

export function IconRefresh(props) {
  return (
    <svg {...defaultProps} {...props}>
      <polyline points="23 4 23 10 17 10" />
      <polyline points="1 20 1 14 7 14" />
      <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
    </svg>
  );
}

export function IconSearch(props) {
  return (
    <svg {...defaultProps} {...props}>
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}

export function IconLogo({ size = 36, className = '' }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 40 40"
      fill="none"
      className={className}
      xmlns="http://www.w3.org/2000/svg"
    >
      <rect width="40" height="40" rx="10" fill="url(#careloop-grad)" />
      <path
        d="M20 9V31M9 20H31"
        stroke="#FFFFFF"
        strokeWidth="3.2"
        strokeLinecap="round"
      />
      <circle
        cx="20"
        cy="20"
        r="9"
        stroke="#E0F2FE"
        strokeWidth="2.2"
        strokeDasharray="4 3"
      />
      <circle cx="20" cy="20" r="3.2" fill="#FFFFFF" />
      <defs>
        <linearGradient id="careloop-grad" x1="0" y1="0" x2="40" y2="40" gradientUnits="userSpaceOnUse">
          <stop stopColor="#0D9488" />
          <stop offset="0.55" stopColor="#0284C7" />
          <stop offset="1" stopColor="#2563EB" />
        </linearGradient>
      </defs>
    </svg>
  );
}
