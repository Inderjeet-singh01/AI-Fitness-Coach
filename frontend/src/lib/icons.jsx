import React from 'react';

const PATHS = {
  logo: <><path d="M4 9h3v6H4zM17 9h3v6h-3zM7 11h10M9 7v10M15 7v10" /><path d="M11 5h2v14h-2z" /></>,
  sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" /></>,
  moon: <path d="M20 15.2A8.5 8.5 0 0 1 8.8 4 8.5 8.5 0 1 0 20 15.2Z" />,
  laptop: <><rect x="3" y="4" width="18" height="12" rx="2" /><path d="M2 20h20" /></>,
  plus: <path d="M12 5v14M5 12h14" />,
  chat: <><path d="M4 5.8A3.8 3.8 0 0 1 7.8 2h8.4A3.8 3.8 0 0 1 20 5.8v5.4a3.8 3.8 0 0 1-3.8 3.8H11l-5.2 4v-4.3A3.8 3.8 0 0 1 4 11.2Z" /><path d="M8 8h8M8 11h5" /></>,
  clipboard: <><path d="M9 4h6a1 1 0 0 1 1 1v1H8V5a1 1 0 0 1 1-1Z" /><rect x="5" y="5" width="14" height="16" rx="2" /><path d="M9 12h6M9 16h6" /></>,
  user: <><circle cx="12" cy="8" r="3.3" /><path d="M5.3 21a6.7 6.7 0 0 1 13.4 0" /></>,
  settings: <><circle cx="12" cy="12" r="3" /><path d="M19.4 13.5a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.87-.34 1.7 1.7 0 0 0-1.04 1.56V19.6a2 2 0 1 1-4 0v-.09a1.7 1.7 0 0 0-1.11-1.56 1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.7 1.7 0 0 0 .34-1.87 1.7 1.7 0 0 0-1.56-1.04H4.4a2 2 0 1 1 0-4h.09a1.7 1.7 0 0 0 1.56-1.11 1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.7 1.7 0 0 0 1.87.34H10.5a1.7 1.7 0 0 0 1.04-1.56V4.4a2 2 0 1 1 4 0v.09a1.7 1.7 0 0 0 1.04 1.56 1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.7 1.7 0 0 0-.34 1.87V10.5a1.7 1.7 0 0 0 1.56 1.04H19.6a2 2 0 1 1 0 4h-.09a1.7 1.7 0 0 0-1.56 1.04Z" /></>,
  target: <><circle cx="12" cy="12" r="8.5" /><circle cx="12" cy="12" r="4.3" /><circle cx="12" cy="12" r="1.2" /></>,
  activity: <path d="M3 12h4l2.1-6 4.1 12 2.3-6H21" />,
  scale: <><path d="M5 20h14M7 17V7a5 5 0 0 1 10 0v10" /><path d="m9.5 11 2.5-2 2.5 2" /></>,
  ruler: <><path d="m7 3 14 14-4 4L3 7z" /><path d="m9 5-2 2M12 8l-2 2M15 11l-2 2M18 14l-2 2" /></>,
  location: <><path d="M19 10.5c0 5.3-7 10.5-7 10.5S5 15.8 5 10.5a7 7 0 1 1 14 0Z" /><circle cx="12" cy="10.5" r="2.2" /></>,
  send: <path d="m4 4 16 8-16 8 3.3-8Z" />,
  arrow: <><path d="M5 12h13" /><path d="m13 6 6 6-6 6" /></>,
  refresh: <><path d="M20 11a8 8 0 0 0-14-4L4 9" /><path d="M4 4v5h5M4 13a8 8 0 0 0 14 4l2-2M20 20v-5h-5" /></>,
  check: <path d="m5 12 4 4L19 6" />,
  bolt: <path d="m13 2-8 11h6l-1 9 8-12h-6Z" />,
  menu: <path d="M4 7h16M4 12h16M4 17h16" />,
  close: <><path d="m6 6 12 12M18 6 6 18" /></>,
  chevron: <path d="m6 9 6 6 6-6" />,
  spark: <><path d="m12 2 1.8 6.2L20 10l-6.2 1.8L12 18l-1.8-6.2L4 10l6.2-1.8Z" /><path d="m19 16 .7 2.3L22 19l-2.3.7L19 22l-.7-2.3L16 19l2.3-.7Z" /></>,
  shield: <path d="M12 3 5 6v5c0 4.7 2.8 8 7 10 4.2-2 7-5.3 7-10V6l-7-3Z" />,
  drop: <path d="M12 3s7 7.4 7 12a7 7 0 0 1-14 0c0-4.6 7-12 7-12Z" />,
  plate: <><circle cx="12" cy="12" r="8" /><circle cx="12" cy="12" r="3.2" /></>,
  dumbbell: <><path d="M4 9v6M7 7v10M17 7v10M20 9v6M7 12h10" /></>,
  gym: <><path d="M2 12h2M20 12h2M6 8v8M18 8v8M6 12h12" /></>,
  question: <><circle cx="12" cy="12" r="9" /><path d="M9.5 9a2.5 2.5 0 1 1 3.9 2.1c-.9.6-1.4 1-1.4 2.1" /><path d="M12 17h.01" /></>,
  trash: <><path d="M4 7h16" /><path d="M10 11v6M14 11v6" /><path d="M6 7l1 13a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-13" /><path d="M9 7V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v3" /></>,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v6M12 8h.01" /></>,
  paperclip: <path d="M21.4 11.1 12.5 20a4.7 4.7 0 0 1-6.6-6.6l9-9a3.1 3.1 0 0 1 4.4 4.4l-8.9 8.9a1.5 1.5 0 0 1-2.2-2.2l7.8-7.8" />,
  mic: <><path d="M12 2.5a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0v-6a3 3 0 0 0-3-3Z" /><path d="M6 11a6 6 0 0 0 12 0M12 19v2.5" /></>,
  bulb: <><path d="M9 18h6M10 21h4" /><path d="M12 3a6 6 0 0 0-3.5 10.9c.6.45 1 1.15 1 1.95v.15h5v-.15c0-.8.4-1.5 1-1.95A6 6 0 0 0 12 3Z" /></>,
  chevronRight: <path d="m9 6 6 6-6 6" />,
};

export function Icon({ name, size = 20, stroke = 1.8, className }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={stroke}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {PATHS[name] || null}
    </svg>
  );
}

export default Icon;
