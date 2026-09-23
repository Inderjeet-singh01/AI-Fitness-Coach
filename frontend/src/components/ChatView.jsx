import React from 'react';
import { Icon } from '../lib/icons.jsx';
import { Report } from '../lib/markdown.jsx';
import { ProgressCard } from './ProgressCard.jsx';

export const QUICK_ACTIONS = [
  { key: 'bmi', label: 'Calculate BMI', icon: 'target', color: 'green', query: 'Calculate my BMI and BMR.' },
  { key: 'diet', label: 'Get Diet Plan', icon: 'plate', color: 'orange', query: 'Create a personalized diet plan for me.' },
  { key: 'workout', label: 'Create Workout Plan', icon: 'dumbbell', color: 'purple', query: 'Create a personalized workout plan for me.' },
  { key: 'water', label: 'Daily Water Intake', icon: 'drop', color: 'blue', query: 'How much water should I drink daily?' },
  { key: 'ask', label: 'Ask Anything', icon: 'question', color: 'gray', query: null },
];

const CAPABILITIES = [
  'BMI & calories calculation',
  'Personalized diet plans',
  'Custom workout plans',
  'Water intake recommendations',
  'Nutrition & fitness guidance',
  'Gym and general fitness questions',
];

const WELCOME_SUGGESTIONS = [
  'Calculate my BMI',
  'Create a diet plan',
  'Create a workout plan',
  'How much water should I drink?',
  'I have a question',
];

const FOLLOW_UPS = ['What should I eat today?', 'Make my workout harder', 'How much water should I drink?'];

function greetingTime() {
  const h = new Date().getHours();
  if (h < 12) return 'Good Morning';
  if (h < 17) return 'Good Afternoon';
  return 'Good Evening';
}

function WelcomeBubble({ name, onSend, loading }) {
  return (
    <>
      <div className="bubble welcome-bubble">
        <p>Hi {name}! <span className="wave">👋</span><br />I'm your AI Fitness Coach.</p>
        <p>I can help you with:</p>
        <ul className="capability-list">
          {CAPABILITIES.map(c => (
            <li key={c}><span className="check-badge"><Icon name="check" size={11} /></span>{c}</li>
          ))}
        </ul>
        <p>What would you like to work on today?</p>
      </div>
      <div className="suggestion-row">
        {WELCOME_SUGGESTIONS.map(s => (
          <button key={s} onClick={() => onSend(s)} disabled={loading}>{s}</button>
        ))}
      </div>
    </>
  );
}

export function ChatView({
  profile, hasProfile, messages, loading, notice, input, setInput,
  onSend, onFocusComposer, composerRef, chatScrollRef, onOpenProfile,
}) {
  function keyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onSend(); }
  }

  function runAction(action) {
    if (action.query === null) { onFocusComposer(); return; }
    onSend(action.query);
  }

  return (
    <section className="chat-area">
      <div className="chat-scroll" ref={chatScrollRef}>
        <div className="chat-intro">
          <h1>{greetingTime()}, {profile.name || 'there'} <span className="wave">👋</span></h1>
          <p>Your AI Fitness Coach is here to help you build a healthier, stronger you.</p>
        </div>

        <div className="action-row">
          {QUICK_ACTIONS.map(a => (
            <button key={a.key} className={`action-tile tile-${a.color}`} onClick={() => runAction(a)} disabled={loading}>
              <span className="tile-icon"><Icon name={a.icon} size={17} /></span>
              <span>{a.label}</span>
            </button>
          ))}
        </div>

        {!hasProfile && (
          <div className="inline-notice">
            <Icon name="info" size={14} />
            <span>Complete your profile to get personalized results.</span>
            <button onClick={onOpenProfile}>Go to Profile</button>
          </div>
        )}

        <div className="messages">
          {messages.map((m) => (
            <div className={`message ${m.role}`} key={m.id}>
              <div className="avatar">{m.role === 'assistant' ? <Icon name="logo" size={14} /> : <Icon name="user" size={15} />}</div>
              <div className={`bubble-wrap ${m.streaming ? 'wide' : ''}`}>
                {m.kind === 'welcome' ? (
                  <WelcomeBubble name={profile.name || 'there'} onSend={onSend} loading={loading} />
                ) : m.role === 'assistant' && m.streaming ? (
                  <ProgressCard steps={m.steps} />
                ) : (
                  <>
                    <div className="bubble">
                      {m.role === 'assistant' ? <Report text={m.content} /> : <p>{m.content}</p>}
                    </div>
                    <time>{m.time}</time>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>

        {notice && <div className="notice chat-notice">{notice}</div>}
      </div>

      <div className="composer-area">
        <div className="quick-row">
          {FOLLOW_UPS.map(x => <button key={x} onClick={() => onSend(x)} disabled={loading}>{x}</button>)}
        </div>
        <div className="composer">
          <button className="composer-icon" disabled title="Attachments aren't supported yet">
            <Icon name="paperclip" size={16} />
          </button>
          <textarea
            ref={composerRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={keyDown}
            placeholder={hasProfile ? 'Type your message…' : 'Complete your profile to start…'}
            disabled={loading}
          />
          <button className="composer-icon" disabled title="Voice input isn't supported yet">
            <Icon name="mic" size={16} />
          </button>
          <button className="send" onClick={() => onSend()} disabled={loading || !input.trim()} aria-label="Send">
            <Icon name="send" size={16} />
          </button>
        </div>
        <div className="composer-footer">
          <span><Icon name="bolt" size={12} /> AI-powered coaching</span>
          <span>Enter to send · Shift + Enter for new line</span>
        </div>
      </div>
    </section>
  );
}

export default ChatView;
