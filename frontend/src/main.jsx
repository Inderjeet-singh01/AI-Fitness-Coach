import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { createSession, deleteSession, getSessionState, streamChat, updateProfile } from './api';
import { uid, stored, timeNow } from './lib/utils.js';
import { advanceSteps, appendStepToken } from './lib/agentPhases.js';
import Sidebar from './components/Sidebar.jsx';
import ContentTop from './components/ContentTop.jsx';
import ChatView from './components/ChatView.jsx';
import MyPlanView from './components/MyPlanView.jsx';
import ProfileView from './components/ProfileView.jsx';
import SettingsView from './components/SettingsView.jsx';
import './styles.css';

const STORAGE = { session: 'fitforge.session_id', profile: 'fitforge.profile', theme: 'fitforge.theme' };

const initialProfile = {
  name: '', age: '', gender: '', weight_kg: '', height_cm: '', activity_level: '', location: '', query: ''
};

const REQUIRED_FIELDS = ['age', 'gender', 'weight_kg', 'height_cm', 'activity_level'];
const FIELD_TITLES = { age: 'age', gender: 'gender', weight_kg: 'weight', height_cm: 'height', activity_level: 'activity level' };

const TAGLINE = [
  { text: 'Consistent' }, { text: 'progress,' }, { text: 'brighter you.', accent: true },
];

function App() {
  const [theme, setThemeState] = useState(() => stored(STORAGE.theme, null) || localStorage.getItem(STORAGE.theme) || 'dark');
  const [systemDark, setSystemDark] = useState(() => window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false);
  const [profile, setProfile] = useState(() => ({ ...initialProfile, ...stored(STORAGE.profile, {}) }));
  const [sessionId, setSessionId] = useState(() => localStorage.getItem(STORAGE.session) || null);
  const [view, setView] = useState('chat');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [messages, setMessages] = useState(() => [
    { id: 'welcome', kind: 'welcome', role: 'assistant', content: '', time: timeNow() },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState('');
  const [planState, setPlanState] = useState({ loading: false, error: '', data: null });
  const [savingProfile, setSavingProfile] = useState(false);
  const [saveMessage, setSaveMessage] = useState('');
  const chatScrollRef = useRef(null);
  const composerRef = useRef(null);

  const resolvedTheme = theme === 'system' ? (systemDark ? 'dark' : 'light') : theme;

  useEffect(() => {
    const mq = window.matchMedia?.('(prefers-color-scheme: dark)');
    if (!mq) return;
    const handler = (e) => setSystemDark(e.matches);
    mq.addEventListener?.('change', handler);
    return () => mq.removeEventListener?.('change', handler);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = resolvedTheme;
    localStorage.setItem(STORAGE.theme, theme);
  }, [theme, resolvedTheme]);

  useEffect(() => {
    const el = chatScrollRef.current;
    if (!el) return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 220;
    if (nearBottom) requestAnimationFrame(() => { el.scrollTop = el.scrollHeight; });
  }, [messages]);

  const update = (field, value) => { setProfile(p => ({ ...p, [field]: value })); setNotice(''); };
  const requiredComplete = REQUIRED_FIELDS.filter(k => profile[k]).length;
  const completion = Math.round((requiredComplete / REQUIRED_FIELDS.length) * 100);
  const hasProfile = completion === 100;

  const initials = useMemo(() => {
    const fromName = (profile.name || '').trim().split(/\s+/).filter(Boolean).slice(0, 2).map(s => s[0]?.toUpperCase()).join('');
    return fromName || 'FC';
  }, [profile.name]);

  // Only backend-recognized profile fields are ever sent to the API.
  const profilePayload = () => {
    const body = { location: profile.location?.trim() || null };
    if (profile.age) body.age = Number(profile.age);
    if (profile.gender) body.gender = profile.gender;
    if (profile.weight_kg) body.weight_kg = Number(profile.weight_kg);
    if (profile.height_cm) body.height_cm = Number(profile.height_cm);
    if (profile.activity_level) body.activity_level = profile.activity_level;
    return body;
  };

  async function ensureSession() {
    const body = profilePayload();
    if (sessionId) {
      try { await updateProfile(sessionId, body); return sessionId; }
      catch (e) { if (e.status !== 404) throw e; }
    }
    const { session_id: nextId } = await createSession(body);
    setSessionId(nextId); localStorage.setItem(STORAGE.session, nextId);
    return nextId;
  }

  async function refreshPlan(id = sessionId) {
    if (!id) return;
    setPlanState(p => ({ ...p, loading: true, error: '' }));
    try {
      const data = await getSessionState(id);
      setPlanState({ loading: false, error: '', data });
    } catch (e) {
      if (e.status === 404) { setPlanState({ loading: false, error: '', data: null }); return; }
      setPlanState(p => ({ ...p, loading: false, error: e.message || 'Could not load your plan.' }));
    }
  }

  function navigate(next) {
    setView(next);
    setSidebarOpen(false);
    if (next === 'plan') refreshPlan();
  }

  async function send(query = input) {
    const clean = query.trim();
    if (!clean || loading) return;
    const missing = REQUIRED_FIELDS.filter(k => !profile[k]).map(k => FIELD_TITLES[k]);
    if (missing.length) {
      setNotice(`Complete your ${missing.join(', ')} first.`);
      navigate('profile');
      return;
    }

    setLoading(true); setNotice(''); setInput('');
    const userMessage = { id: uid(), role: 'user', content: clean, time: timeNow() };
    const assistantId = uid();
    setMessages(m => [...m, userMessage, { id: assistantId, role: 'assistant', content: '', time: timeNow(), streaming: true, steps: [] }]);

    const pushPhase = (phase, node) => {
      setMessages(m => m.map(msg => msg.id === assistantId ? { ...msg, steps: advanceSteps(msg.steps, phase, node) } : msg));
    };

    try {
      const activeId = await ensureSession();
      const data = await streamChat(activeId, clean, {
        onToken: (token) => setMessages(m => m.map(msg => msg.id === assistantId ? { ...msg, steps: appendStepToken(msg.steps, token) } : msg)),
        onPhase: pushPhase,
      });
      const nextProfile = { ...profile, query: clean };
      setProfile(nextProfile); localStorage.setItem(STORAGE.profile, JSON.stringify(nextProfile));
      setMessages(m => m.map(msg => msg.id === assistantId ? {
        ...msg,
        content: data.final_report || msg.content || 'Your plan is ready.',
        streaming: false,
        steps: advanceSteps(msg.steps, 'completed'),
        time: timeNow(),
      } : msg));
      refreshPlan(activeId);
    } catch (e) {
      setNotice(e.message || 'Unable to reach your fitness coach.');
      setMessages(m => m.filter(msg => msg.id !== assistantId && msg.id !== userMessage.id));
    } finally {
      setLoading(false);
    }
  }

  async function newChat() {
    try { await deleteSession(sessionId); } catch { /* already gone, ignore */ }
    setSessionId(null); localStorage.removeItem(STORAGE.session);
    setMessages([{ id: 'welcome', kind: 'welcome', role: 'assistant', content: '', time: timeNow() }]);
    setInput(''); setNotice('');
    setPlanState({ loading: false, error: '', data: null });
    setProfile(p => ({ ...p, query: '' }));
    setView('chat');
  }

  async function saveProfile() {
    setSavingProfile(true); setSaveMessage('');
    try {
      await ensureSession();
      localStorage.setItem(STORAGE.profile, JSON.stringify(profile));
      setSaveMessage('Saved');
      refreshPlan();
    } catch (e) {
      setSaveMessage(e.message || 'Could not save your details.');
    } finally {
      setSavingProfile(false);
      setTimeout(() => setSaveMessage(''), 2500);
    }
  }

  return (
    <div className="app">
      <Sidebar view={view} onNavigate={navigate} open={sidebarOpen} onClose={() => setSidebarOpen(false)} resolvedTheme={resolvedTheme} />
      <main className="content">
        <ContentTop
          theme={theme}
          onThemeChange={setThemeState}
          initials={initials}
          onMenuClick={() => setSidebarOpen(true)}
          onNewChat={newChat}
          showNewChat={view === 'chat'}
          tagline={view === 'chat' ? TAGLINE : null}
        />
        <div className="view-body">
          {view === 'chat' && (
            <ChatView
              profile={profile}
              hasProfile={hasProfile}
              messages={messages}
              loading={loading}
              notice={notice}
              input={input}
              setInput={setInput}
              onSend={send}
              onFocusComposer={() => composerRef.current?.focus()}
              composerRef={composerRef}
              chatScrollRef={chatScrollRef}
              onOpenProfile={() => navigate('profile')}
            />
          )}
          {view === 'plan' && (
            <MyPlanView planState={planState} onRefresh={() => refreshPlan()} onGoToChat={() => navigate('chat')} />
          )}
          {view === 'profile' && (
            <ProfileView
              profile={profile}
              update={update}
              completion={completion}
              onSave={saveProfile}
              saving={savingProfile}
              saveMessage={saveMessage}
            />
          )}
          {view === 'settings' && (
            <SettingsView theme={theme} onThemeChange={setThemeState} onResetSession={newChat} sessionId={sessionId} />
          )}
        </div>
        <footer>
          <span>AI Fitness Coach · Personal fitness guidance</span>
          <span>AI can make mistakes. Verify important health decisions with a qualified professional.</span>
        </footer>
      </main>
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
