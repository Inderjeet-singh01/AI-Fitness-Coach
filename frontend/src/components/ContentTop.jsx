import React from 'react';
import { Icon } from '../lib/icons.jsx';

const THEME_OPTIONS = [
  ['light', 'sun', 'Light mode'],
  ['dark', 'moon', 'Dark mode'],
  ['system', 'laptop', 'Match system'],
];

export function ContentTop({ theme, onThemeChange, initials, onMenuClick, onNewChat, showNewChat, tagline }) {
  return (
    <div className="content-top">
      <button className="menu-btn" onClick={onMenuClick} aria-label="Open menu"><Icon name="menu" size={19} /></button>
      <div className="content-top-right">
        {tagline && (
          <p className="tagline">
            {tagline.map((line, i) => (
              <span key={i} className={line.accent ? 'accent' : ''}>{line.text}</span>
            ))}
          </p>
        )}
        <div className="top-controls">
          {showNewChat && (
            <button className="icon-btn" onClick={onNewChat} title="Start a new conversation">
              <Icon name="plus" size={16} />
            </button>
          )}
          <div className="mode-switch" role="radiogroup" aria-label="Theme">
            {THEME_OPTIONS.map(([value, icon, title]) => (
              <button
                key={value}
                className={theme === value ? 'active' : ''}
                onClick={() => onThemeChange(value)}
                title={title}
                aria-pressed={theme === value}
              >
                <Icon name={icon} size={13} />
              </button>
            ))}
          </div>
          <div className="avatar-badge" title="Your session">{initials}</div>
        </div>
      </div>
    </div>
  );
}

export default ContentTop;
