import React from 'react';
import { useTheme } from '../ThemeContext';
import { IconSun, IconMoon } from './Icons';

export default function ThemeToggle({ className = '', style = {} }) {
  const { isDark, toggleTheme } = useTheme();

  return (
    <button
      type="button"
      onClick={toggleTheme}
      title={isDark ? 'Switch to Clinical Light Mode' : 'Switch to Dark Mode'}
      aria-label="Toggle theme"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px',
        padding: '6px 12px',
        borderRadius: '20px',
        border: '1px solid var(--border-subtle, #cbd5e1)',
        background: 'var(--bg-card, #ffffff)',
        color: 'var(--text-primary, #0f172a)',
        fontSize: '12px',
        fontWeight: 600,
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
        ...style,
      }}
      className={className}
    >
      {isDark ? (
        <>
          <IconSun width={15} height={15} style={{ color: '#fbbf24' }} />
          <span>Light</span>
        </>
      ) : (
        <>
          <IconMoon width={15} height={15} style={{ color: '#0284c7' }} />
          <span>Dark</span>
        </>
      )}
    </button>
  );
}
