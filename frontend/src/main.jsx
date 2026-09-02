import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { clearSession, streamPlan } from './api';
import './styles.css';

const STORAGE = { session: 'fitforge.session_id', profile: 'fitforge.profile', theme: 'fitforge.theme' };

const initialProfile = {
  age: '', gender: '', weight_kg: '', height_cm: '', activity_level: '', location: '', query: ''
};

const activityOptions = [
  ['sedentary', 'Sedentary', 'Little or no exercise'],
  ['lightly_active', 'Lightly active', '1–3 workouts / week'],
  ['moderately_active', 'Moderately active', '3–5 workouts / week'],
  ['very_active', 'Very active', '6–7 workouts / week'],
];

const goalChips = [
  ['Lose weight', 'I want to lose weight and improve my body composition.'],
  ['Build muscle', 'I want to build muscle and get stronger.'],
  ['Get fit', 'I want to improve my overall fitness and energy.'],
  ['Improve endurance', 'I want to improve my cardio and endurance.'],
];

function Icon({ name, size = 20, stroke = 1.8 }) {
  const p = {
    logo: <><path d="M4 9h3v6H4zM17 9h3v6h-3zM7 11h10M9 7v10M15 7v10"/><path d="M11 5h2v14h-2z"/></>,
    sun: <><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/></>,
    moon: <path d="M20 15.2A8.5 8.5 0 0 1 8.8 4 8.5 8.5 0 1 0 20 15.2Z"/>,
    plus: <><path d="M12 5v14M5 12h14"/></>,
    chat: <><path d="M4 5.8A3.8 3.8 0 0 1 7.8 2h8.4A3.8 3.8 0 0 1 20 5.8v5.4a3.8 3.8 0 0 1-3.8 3.8H11l-5.2 4v-4.3A3.8 3.8 0 0 1 4 11.2Z"/><path d="M8 8h8M8 11h5"/></>,
    user: <><circle cx="12" cy="8" r="3.3"/><path d="M5.3 21a6.7 6.7 0 0 1 13.4 0"/></>,
    target: <><circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.3"/><circle cx="12" cy="12" r="1.2"/></>,
    activity: <path d="M3 12h4l2.1-6 4.1 12 2.3-6H21"/>,
    scale: <><path d="M5 20h14M7 17V7a5 5 0 0 1 10 0v10"/><path d="m9.5 11 2.5-2 2.5 2"/></>,
    ruler: <><path d="m7 3 14 14-4 4L3 7z"/><path d="m9 5-2 2M12 8l-2 2M15 11l-2 2M18 14l-2 2"/></>,
    location: <><path d="M19 10.5c0 5.3-7 10.5-7 10.5S5 15.8 5 10.5a7 7 0 1 1 14 0Z"/><circle cx="12" cy="10.5" r="2.2"/></>,
    send: <path d="m4 4 16 8-16 8 3.3-8Z"/>,
    arrow: <><path d="M5 12h13"/><path d="m13 6 6 6-6 6"/></>,
    refresh: <><path d="M20 11a8 8 0 0 0-14-4L4 9"/><path d="M4 4v5h5M4 13a8 8 0 0 0 14 4l2-2M20 20v-5h-5"/></>,
    check: <path d="m5 12 4 4L19 6"/>,
    bolt: <path d="m13 2-8 11h6l-1 9 8-12h-6Z"/>,
    menu: <><path d="M4 7h16M4 12h16M4 17h16"/></>,
    close: <><path d="m6 6 12 12M18 6 6 18"/></>,
    chevron: <path d="m6 9 6 6 6-6"/>,
    spark: <><path d="m12 2 1.8 6.2L20 10l-6.2 1.8L12 18l-1.8-6.2L4 10l6.2-1.8Z"/><path d="m19 16 .7 2.3L22 19l-2.3.7L19 22l-.7-2.3L16 19l2.3-.7Z"/></>,
    shield: <path d="M12 3 5 6v5c0 4.7 2.8 8 7 10 4.2-2 7-5.3 7-10V6l-7-3Z"/>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{p[name]}</svg>;
}

function uid() {
  return crypto?.randomUUID?.() || `ff-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function stored(key, fallback) {
  try { const v = localStorage.getItem(key); return v ? JSON.parse(v) : fallback; } catch { return fallback; }
}

function timeNow() { return new Intl.DateTimeFormat([], { hour: 'numeric', minute: '2-digit' }).format(new Date()); }

function renderInline(text) {
  const chunks = String(text || '').split(/(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^\)]+\))/g);
  return chunks.map((c, i) => {
    if (c.startsWith('**') && c.endsWith('**')) return <strong key={i}>{c.slice(2, -2)}</strong>;
    if (c.startsWith('`') && c.endsWith('`')) return <code key={i}>{c.slice(1, -1)}</code>;
    const m = c.match(/^\[([^\]]+)\]\(([^\)]+)\)$/);
    if (m) return <a key={i} href={m[2]} target="_blank" rel="noreferrer">{m[1]}</a>;
    return <React.Fragment key={i}>{c}</React.Fragment>;
  });
}

function Report({ text }) {
  const clean = String(text || '').replace(/\r/g, '').replace(/^\s*---+\s*$/gm, '').trim();
  const lines = clean.split('\n');
  const nodes = [];
  let paragraph = [];
  let list = [];

  const flushParagraph = () => {
    if (!paragraph.length) return;
    nodes.push(<p key={`p-${nodes.length}`}>{paragraph.map((line, i) => <React.Fragment key={i}>{i > 0 && <br/>}{renderInline(line)}</React.Fragment>)}</p>);
    paragraph = [];
  };
  const flushList = () => {
    if (!list.length) return;
    const ordered = list[0].match(/^\d+[.)]\s+/);
    const Tag = ordered ? 'ol' : 'ul';
    nodes.push(<Tag key={`l-${nodes.length}`}>{list.map((item, i) => <li key={i}>{renderInline(item.replace(/^(?:[-*]|\d+[.)])\s+/, ''))}</li>)}</Tag>);
    list = [];
  };

  lines.forEach((raw, idx) => {
    const line = raw.trim();
    if (!line) { flushList(); flushParagraph(); return; }
    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      flushList(); flushParagraph();
      const H = `h${heading[1].length}`;
      nodes.push(React.createElement(H, { key: `h-${idx}` }, renderInline(heading[2])));
      return;
    }
    if (/^[-*]\s+/.test(line) || /^\d+[.)]\s+/.test(line)) {
      flushParagraph();
      const type = /^\d+[.)]\s+/.test(line) ? 'ordered' : 'unordered';
      if (list.length && ((/^\d+[.)]\s+/.test(list[0])) !== (type === 'ordered'))) flushList();
      list.push(line);
      return;
    }
    flushList();
    if (line.startsWith('> ')) paragraph.push(line.slice(2));
    else paragraph.push(line);
  });
  flushList(); flushParagraph();
  return <div className="report-text">{nodes}</div>;
}
function Metric({ label, value, unit, icon }) {
  return <div className="metric"><div className="metric-icon"><Icon name={icon} size={17}/></div><div><span>{label}</span><strong>{value}{unit && <em>{unit}</em>}</strong></div></div>;
}

function App() {
  const [theme, setTheme] = useState(() => localStorage.getItem(STORAGE.theme) || 'dark');
  const [profile, setProfile] = useState(() => ({ ...initialProfile, ...stored(STORAGE.profile, {}) }));
  const [sessionId, setSessionId] = useState(() => localStorage.getItem(STORAGE.session) || uid());
  const [messages, setMessages] = useState([]);
  const [result, setResult] = useState(null);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState('');
  const [mobileProfile, setMobileProfile] = useState(false);
  const endRef = useRef(null);
  const chatScrollRef = useRef(null);

  useEffect(() => { document.documentElement.dataset.theme = theme; localStorage.setItem(STORAGE.theme, theme); }, [theme]);
  useEffect(() => {
    const el = chatScrollRef.current;
    if (!el) return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 180;
    if (nearBottom) {
      requestAnimationFrame(() => { el.scrollTop = el.scrollHeight; });
    }
  }, [messages, result]);

  const update = (field, value) => { setProfile(p => ({ ...p, [field]: value })); setNotice(''); };
  const firstName = profile.name || 'there';
  const requiredFields = ['age','gender','weight_kg','height_cm','activity_level'];
  const completion = Math.round(requiredFields.filter(k => profile[k]).length / requiredFields.length * 100);
  const hasProfile = completion === 100;
  const metrics = useMemo(() => {
    if (!result) return [];

    // Read metrics from the API response first.
    // The fallback calculations below keep the dashboard populated even
    // if the final SSE payload does not contain the metric objects.
    const response = result?.data && typeof result.data === 'object' ? result.data : result;
    const bmi = response?.bmi_data || result?.bmi_data || {};
    const water = response?.water_data || result?.water_data || {};
    const macro = response?.macro_data || result?.macro_data || {};

    const weight = Number(profile.weight_kg);
    const height = Number(profile.height_cm);
    const age = Number(profile.age);
    const gender = String(profile.gender || '').toLowerCase();

    const validWeight = Number.isFinite(weight) && weight > 0;
    const validHeight = Number.isFinite(height) && height > 0;
    const validAge = Number.isFinite(age) && age > 0;

    // Fallback values use the same standard calculations used by the
    // fitness tools. API values always take priority when available.
    const fallbackBmi = validWeight && validHeight
      ? Number((weight / ((height / 100) ** 2)).toFixed(2))
      : null;

    const fallbackBmr = validWeight && validHeight && validAge
      ? Number((10 * weight + 6.25 * height - 5 * age + (gender === 'female' ? -161 : 5)).toFixed(2))
      : null;

    const fallbackWater = validWeight
      ? Number((weight * 0.035).toFixed(2))
      : null;

    const fallbackProtein = validWeight
      ? Number((weight * 2).toFixed(2))
      : null;

    const bmiValue = bmi.bmi_value ?? bmi.bmi ?? fallbackBmi;
    const bmrValue = bmi.bmr ?? bmi.basal_metabolic_rate ?? fallbackBmr;
    const waterValue = water.water_intake_liters ?? water.water_liters ?? water.daily_water_liters ?? fallbackWater;
    const proteinValue = macro.protein_g ?? macro.protein ?? fallbackProtein;

    return [
      {
        label: 'BMI',
        value: bmiValue ?? '—',
        unit: '',
        icon: 'target'
      },
      {
        label: 'BMR',
        value: bmrValue ?? '—',
        unit: bmrValue != null ? ' kcal' : '',
        icon: 'bolt'
      },
      {
        label: 'Hydration',
        value: waterValue ?? '—',
        unit: waterValue != null ? ' L/day' : '',
        icon: 'activity'
      },
      {
        label: 'Protein',
        value: proteinValue ?? '—',
        unit: proteinValue != null ? ' g/day' : '',
        icon: 'scale'
      },
    ];
  }, [result, profile.weight_kg, profile.height_cm, profile.age, profile.gender]);

  const payload = (query) => ({
    session_id: sessionId,
    age: Number(profile.age), gender: profile.gender, weight_kg: Number(profile.weight_kg), height_cm: Number(profile.height_cm),
    activity_level: profile.activity_level, location: profile.location?.trim() || null, query: query.trim()
  });

  async function send(query = input) {
    const clean = query.trim();
    if (!clean || loading) return;
    const missing = [];
    if (!profile.age) missing.push('age');
    if (!profile.gender) missing.push('gender');
    if (!profile.height_cm) missing.push('height');
    if (!profile.weight_kg) missing.push('weight');
    if (!profile.activity_level) missing.push('activity level');
    if (missing.length) { setNotice(`Complete your ${missing.join(', ')} first.`); setMobileProfile(true); return; }

    setLoading(true); setNotice(''); setInput('');
    const userMessage = { role: 'user', content: clean, time: timeNow() };
    const assistantId = uid();
    setMessages(m => [...m, userMessage, { id: assistantId, role: 'assistant', content: '', time: timeNow(), streaming: true }]);

    try {
      const data = await streamPlan(payload(clean), {
        onToken: (token) => setMessages(m => m.map(msg => msg.id === assistantId ? { ...msg, content: msg.content + token } : msg)),
      });
      const nextId = data.session_id || sessionId;
      setSessionId(nextId); localStorage.setItem(STORAGE.session, nextId);
      const nextProfile = { ...profile, query: clean };
      setProfile(nextProfile); localStorage.setItem(STORAGE.profile, JSON.stringify(nextProfile));
      setResult(data);
      setMessages(m => m.map(msg => msg.id === assistantId ? { ...msg, content: data.final_report || msg.content || 'Your plan is ready.', streaming: false, time: timeNow() } : msg));
    } catch (e) {
      setNotice(e.message || 'Unable to reach your fitness coach.');
      setMessages(m => m.filter(msg => msg.id !== assistantId && msg !== userMessage));
    } finally { setLoading(false); }
  }

  async function newChat() {
    try { await clearSession(sessionId); } catch {}
    const next = uid(); setSessionId(next); localStorage.setItem(STORAGE.session, next);
    setMessages([]); setResult(null); setInput(''); setNotice(''); setProfile(p => ({ ...p, query: '' }));
  }

  function keyDown(e) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }

  return <div className="app">
    <header className="topbar">
      <div className="brand"><div className="brand-mark"><Icon name="logo" size={22}/></div><div><strong>AI Fitness Coach</strong><small>Personal Fitness Coach</small></div></div>
      <div className="top-actions">
        <div className="mode-switch" aria-label="Theme switcher"><button className={theme==='light'?'active':''} onClick={()=>setTheme('light')} title="Light mode"><Icon name="sun" size={15}/></button><button className={theme==='dark'?'active':''} onClick={()=>setTheme('dark')} title="Dark mode"><Icon name="moon" size={15}/></button></div>
        <button className="new-chat" onClick={newChat}><Icon name="plus" size={16}/> New chat</button>
      </div>
    </header>

    <div className="mobile-profile-trigger"><button onClick={()=>setMobileProfile(true)}><Icon name="user" size={17}/> Your details <span>{hasProfile ? 'Complete' : 'Required'}</span></button></div>

    <main className="shell">
      <aside className={`profile-panel ${mobileProfile ? 'open' : ''}`}>
        <div className="profile-head"><div><span className="eyebrow">COACH SETUP</span><h2>Your details</h2><p>Tell me about yourself so I can personalize every recommendation.</p></div><button className="close-mobile" onClick={()=>setMobileProfile(false)}><Icon name="close" size={19}/></button></div>
        <div className="completion"><div><span>Profile completion</span><strong>{completion}%</strong></div><div className="progress"><i style={{ width: `${completion}%` }}/></div></div>

        <div className="field-grid">
          <label className="field full"><span>Name</span><div className="input-wrap"><Icon name="user" size={16}/><input value={profile.name || ''} onChange={e=>update('name',e.target.value)} placeholder="Your name" /></div></label>
          <label className="field"><span>Age</span><div className="input-wrap"><Icon name="user" size={16}/><input type="number" min="2" max="119" value={profile.age} onChange={e=>update('age',e.target.value)} placeholder="25" /></div></label>
          <label className="field"><span>Gender</span><div className="input-wrap select"><Icon name="user" size={16}/><select value={profile.gender} onChange={e=>update('gender',e.target.value)}><option value="">Select</option><option value="male">Male</option><option value="female">Female</option><option value="other">Other</option></select><Icon name="chevron" size={14}/></div></label>
          <label className="field"><span>Height <em>cm</em></span><div className="input-wrap"><Icon name="ruler" size={16}/><input type="number" min="51" max="249" value={profile.height_cm} onChange={e=>update('height_cm',e.target.value)} placeholder="175" /></div></label>
          <label className="field"><span>Weight <em>kg</em></span><div className="input-wrap"><Icon name="scale" size={16}/><input type="number" min="11" max="299" value={profile.weight_kg} onChange={e=>update('weight_kg',e.target.value)} placeholder="70" /></div></label>
          <label className="field full"><span>Daily activity level</span><div className="input-wrap select"><Icon name="activity" size={16}/><select value={profile.activity_level} onChange={e=>update('activity_level',e.target.value)}><option value="">Select activity</option>{activityOptions.map(([v,l])=><option key={v} value={v}>{l}</option>)}</select><Icon name="chevron" size={14}/></div></label>
          <label className="field full"><span>Location <em>optional</em></span><div className="input-wrap"><Icon name="location" size={16}/><input value={profile.location || ''} onChange={e=>update('location',e.target.value)} placeholder="City or area" /></div></label>
        </div>

        <div className="privacy"><Icon name="shield" size={15}/><span>Your details stay in your session and are used to personalize your plan.</span></div>
        {notice && <div className="notice">{notice}</div>}
      </aside>

      {mobileProfile && <button className="scrim" onClick={()=>setMobileProfile(false)} aria-label="Close profile"/>}

      <section className="chat-area">
        <div className="chat-header"><div className="coach-avatar"><Icon name="spark" size={20}/></div><div><strong>AI Fitness Coach</strong><span><i/> Online · Ready to help</span></div><div className="chat-header-actions"><button title="New conversation" onClick={newChat}><Icon name="refresh" size={17}/></button></div></div>

        <div className="chat-scroll" ref={chatScrollRef}>
          {messages.length === 0 ? <div className="welcome">
            <div className="welcome-orb"><div><Icon name="spark" size={28}/></div></div>
            <span className="eyebrow">AI FITNESS COACH</span>
            <h1>Your goals.<br/><span>My guidance.</span></h1>
            <p>Tell me what you want to achieve. I'll use your details to create a practical, personalized fitness plan.</p>
            <div className="welcome-note"><span className="dot"/><span>Complete your details on the left, then start chatting.</span></div>
            <div className="suggestions">
              {goalChips.map(([label, q]) => <button key={label} onClick={()=>{update('query', q); send(q)}}>{label}<Icon name="arrow" size={14}/></button>)}
            </div>
          </div> : <div className="messages">
            <div className="day-label">TODAY</div>
            {messages.map((m,i)=><div className={`message ${m.role}`} key={i}><div className="avatar">{m.role==='assistant'?<Icon name="spark" size={15}/>:<Icon name="user" size={15}/>}</div><div className="bubble-wrap"><div className="bubble">{m.role==='assistant' ? (m.streaming ? <p className="streaming-copy">{m.content}<span className="stream-cursor" aria-hidden="true"/></p> : <Report text={m.content}/>) : <p>{m.content}</p>}</div><time>{m.time}</time></div></div>)}
            <div ref={endRef}/>
          </div>}

          {result && <div className="insight-card"><div className="insight-head"><div><span className="eyebrow">YOUR SNAPSHOT</span><h3>Coach metrics</h3></div><span className="ready"><Icon name="check" size={13}/> Calculated</span></div><div className="metrics">{metrics.map((m,i)=><Metric key={i} {...m}/>)}</div></div>}
        </div>

        <div className="composer-area">
          <div className="quick-row">{['What should I eat today?', 'Make my workout harder', 'How much water should I drink?'].map(x=><button key={x} onClick={()=>send(x)} disabled={loading}>{x}</button>)}</div>
          <div className="composer"><textarea value={input} onChange={e=>setInput(e.target.value)} onKeyDown={keyDown} placeholder={hasProfile ? 'Ask your fitness coach anything…' : 'Complete your details to start…'} disabled={loading}/><button className="send" onClick={()=>send()} disabled={loading || !input.trim()} aria-label="Send"><Icon name="send" size={18}/></button></div>
          <div className="composer-footer"><span><Icon name="bolt" size={12}/> AI-powered coaching</span><span>Enter to send · Shift + Enter for new line</span></div>
        </div>
      </section>
    </main>

    <footer><span>AI Fitness Coach · Personal fitness guidance</span><span>AI can make mistakes. Verify important health decisions with a qualified professional.</span></footer>
  </div>;
}

createRoot(document.getElementById('root')).render(<App />);
