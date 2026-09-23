import React from 'react';
import { Icon } from '../lib/icons.jsx';

const activityOptions = [
  ['sedentary', 'Sedentary', 'Little or no exercise'],
  ['lightly_active', 'Lightly active', '1–3 workouts / week'],
  ['moderately_active', 'Moderately active', '3–5 workouts / week'],
  ['very_active', 'Very active', '6–7 workouts / week'],
];

export function ProfileView({ profile, update, completion, onSave, saving, saveMessage }) {
  return (
    <section className="page-view">
      <div className="page-head">
        <div>
          <span className="eyebrow">COACH SETUP</span>
          <h2>Your Profile</h2>
          <p>Tell me about yourself so I can personalize every recommendation.</p>
        </div>
      </div>

      <div className="card">
        <div className="completion">
          <div><span>Profile completion</span><strong>{completion}%</strong></div>
          <div className="progress"><i style={{ width: `${completion}%` }} /></div>
        </div>

        <div className="field-grid">
          <label className="field full">
            <span>Display name <em>optional, stays on this device</em></span>
            <div className="input-wrap"><Icon name="user" size={16} /><input value={profile.name || ''} onChange={e => update('name', e.target.value)} placeholder="Your name" /></div>
          </label>
          <label className="field">
            <span>Age</span>
            <div className="input-wrap"><Icon name="user" size={16} /><input type="number" min="2" max="119" value={profile.age} onChange={e => update('age', e.target.value)} placeholder="25" /></div>
          </label>
          <label className="field">
            <span>Gender</span>
            <div className="input-wrap select">
              <Icon name="user" size={16} />
              <select value={profile.gender} onChange={e => update('gender', e.target.value)}>
                <option value="">Select</option>
                <option value="male">Male</option>
                <option value="female">Female</option>
                <option value="other">Other</option>
              </select>
              <Icon name="chevron" size={14} />
            </div>
          </label>
          <label className="field">
            <span>Height <em>cm</em></span>
            <div className="input-wrap"><Icon name="ruler" size={16} /><input type="number" min="51" max="249" value={profile.height_cm} onChange={e => update('height_cm', e.target.value)} placeholder="175" /></div>
          </label>
          <label className="field">
            <span>Weight <em>kg</em></span>
            <div className="input-wrap"><Icon name="scale" size={16} /><input type="number" min="11" max="299" value={profile.weight_kg} onChange={e => update('weight_kg', e.target.value)} placeholder="70" /></div>
          </label>
          <label className="field full">
            <span>Daily activity level</span>
            <div className="input-wrap select">
              <Icon name="activity" size={16} />
              <select value={profile.activity_level} onChange={e => update('activity_level', e.target.value)}>
                <option value="">Select activity</option>
                {activityOptions.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
              <Icon name="chevron" size={14} />
            </div>
          </label>
          <label className="field full">
            <span>Location <em>optional, for nearby gyms</em></span>
            <div className="input-wrap"><Icon name="location" size={16} /><input value={profile.location || ''} onChange={e => update('location', e.target.value)} placeholder="City or area" /></div>
          </label>
        </div>

        <div className="privacy"><Icon name="shield" size={15} /><span>Your details stay in your session and are used to personalize your plan.</span></div>

        <div className="profile-actions">
          <button className="primary-btn" onClick={onSave} disabled={saving}>
            {saving ? 'Saving…' : 'Save changes'}
          </button>
          {saveMessage && <span className="save-message">{saveMessage}</span>}
        </div>
      </div>
    </section>
  );
}

export default ProfileView;
