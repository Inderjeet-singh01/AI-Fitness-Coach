import React from 'react';
import { Icon } from '../lib/icons.jsx';
import heroStrength from '../assets/hero-strength.jpg';
import heroTrail from '../assets/hero-trail.jpg';

const NAV_ITEMS = [
  { key: 'chat', label: 'Chat', icon: 'chat' },
  { key: 'plan', label: 'My Plan', icon: 'clipboard' },
  { key: 'profile', label: 'Profile', icon: 'user' },
  { key: 'settings', label: 'Settings', icon: 'settings' },
];

export function Sidebar({ view, onNavigate, open, onClose, resolvedTheme }) {
  const heroSrc = resolvedTheme === 'light' ? heroTrail : heroStrength;

  return (
    <>
      {open && <button className="scrim" onClick={onClose} aria-label="Close menu" />}
      <aside className={`sidebar ${open ? 'open' : ''}`}>
        <div className="sidebar-brand">
          <div className="brand-mark"><Icon name="logo" size={19} /></div>
          <div>
            <strong>AI Fitness Coach</strong>
            <small>Smarter. Healthier. You.</small>
          </div>
          <button className="close-mobile" onClick={onClose} aria-label="Close menu"><Icon name="close" size={17} /></button>
        </div>
        <nav className="sidebar-nav">
          {NAV_ITEMS.map(item => (
            <button
              key={item.key}
              className={`nav-item ${view === item.key ? 'active' : ''}`}
              onClick={() => onNavigate(item.key)}
            >
              <Icon name={item.icon} size={16} />
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-hero">
          <img src={heroSrc} alt="" />
          <div className="sidebar-hero-fade" />
          <div className="sidebar-hero-quote">
            <span>Consistency</span>
            <span>today.</span>
            <span className="accent">Results</span>
            <span className="accent">tomorrow.</span>
          </div>
        </div>
      </aside>
    </>
  );
}

export default Sidebar;
