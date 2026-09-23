import React, { useEffect, useRef } from 'react';
import { Icon } from '../lib/icons.jsx';

export function ProgressCard({ steps }) {
  const scrollRef = useRef(null);
  const followRef = useRef(true);
  const activeKey = steps?.find(s => s.status === 'active')?.key;

  function handleScroll() {
    const el = scrollRef.current;
    if (!el) return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 24;
    followRef.current = nearBottom;
  }

  useEffect(() => {
    const el = scrollRef.current;
    if (!el || !followRef.current) return;
    const activeEl = el.querySelector('[data-active="true"]');
    if (activeEl) activeEl.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [activeKey, steps]);

  if (!steps || !steps.length) return null;

  return (
    <div className="progress-card">
      <div className="progress-head">
        <div className="avatar-lg"><Icon name="logo" size={17} /></div>
        <div>
          <strong>AI is working on your request…</strong>
          <p>I'll show each step as it completes. Scroll to follow along.</p>
        </div>
      </div>

      <ol className="timeline" ref={scrollRef} onScroll={handleScroll}>
        {steps.map((s) => (
          <li key={s.key} className={`timeline-item ${s.status}`} data-active={s.status === 'active'}>
            <span className="timeline-dot">
              {s.status === 'done' ? <Icon name="check" size={11} /> : s.status === 'active' ? <span className="pulse" /> : null}
            </span>
            <div className="timeline-body">
              <div className="timeline-row">
                <span className="timeline-label">{s.label}</span>
                <time>{s.time}</time>
              </div>
              {s.detail && (
                <p className={`timeline-detail ${s.status}`}>{s.detail}</p>
              )}
            </div>
          </li>
        ))}
      </ol>

      <div className="progress-hint"><Icon name="bulb" size={14} /> Working on it — this usually takes 20–40 seconds.</div>
    </div>
  );
}

export default ProgressCard;
