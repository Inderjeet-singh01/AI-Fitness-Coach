import React from 'react';
import { Icon } from '../lib/icons.jsx';

const THEME_OPTIONS = [
  ['light', 'sun', 'Light', 'Bright surfaces with green accents.'],
  ['dark', 'moon', 'Dark', 'Near-black surfaces with neon green accents.'],
  ['system', 'laptop', 'System', 'Matches your device setting.'],
];

export function SettingsView({ theme, onThemeChange, onResetSession, sessionId }) {
  return (
    <section className="page-view">
      <div className="page-head">
        <div>
          <span className="eyebrow">PREFERENCES</span>
          <h2>Settings</h2>
          <p>Simple controls for how the app looks and your current session.</p>
        </div>
      </div>

      <div className="card">
        <h3>Appearance</h3>
        <div className="theme-options">
          {THEME_OPTIONS.map(([value, icon, label, desc]) => (
            <button
              key={value}
              className={`theme-option ${theme === value ? 'active' : ''}`}
              onClick={() => onThemeChange(value)}
            >
              <span className="theme-option-icon"><Icon name={icon} size={18} /></span>
              <span>
                <strong>{label}</strong>
                <small>{desc}</small>
              </span>
              {theme === value && <Icon name="check" size={16} className="theme-check" />}
            </button>
          ))}
        </div>
      </div>

      <div className="card">
        <h3>Session</h3>
        <p className="muted-text">{sessionId ? 'Your conversation and profile are tied to this browser session.' : 'No active session yet — starting a chat will create one.'}</p>
        <button className="danger-btn" onClick={onResetSession}>
          <Icon name="trash" size={15} /> Clear conversation &amp; start a new session
        </button>
      </div>
    </section>
  );
}

export default SettingsView;
