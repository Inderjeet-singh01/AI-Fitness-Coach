import React from 'react';
import { Icon } from '../lib/icons.jsx';
import { Report } from '../lib/markdown.jsx';

function Metric({ label, value, unit, icon }) {
  if (value === null || value === undefined) return null;
  return (
    <div className="metric">
      <div className="metric-icon"><Icon name={icon} size={17} /></div>
      <div><span>{label}</span><strong>{value}{unit && <em>{unit}</em>}</strong></div>
    </div>
  );
}

export function MyPlanView({ planState, onRefresh, onGoToChat }) {
  const { loading, error, data } = planState;
  const bmi = data?.bmi_data;
  const water = data?.water_data;
  const macro = data?.macro_data;
  const dietPlan = data?.diet_plan;
  const workoutPlan = data?.workout_plan;
  const gymData = data?.gym_data;

  const hasMetrics = Boolean(bmi || water || macro);
  const hasAnyPlan = Boolean(hasMetrics || dietPlan || workoutPlan || gymData);

  return (
    <section className="page-view">
      <div className="page-head">
        <div>
          <span className="eyebrow">YOUR PROGRESS</span>
          <h2>My Plan</h2>
          <p>Everything your coach has calculated and generated for you so far.</p>
        </div>
        <button className="ghost-btn" onClick={onRefresh} disabled={loading}>
          <Icon name="refresh" size={15} /> {loading ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      {error && <div className="notice">{error}</div>}

      {!loading && !hasAnyPlan && !error && (
        <div className="empty-state">
          <div className="welcome-orb"><Icon name="clipboard" size={22} /></div>
          <h3>No plan yet</h3>
          <p>Ask your coach for a BMI check, diet plan, or workout plan in Chat and it will show up here.</p>
          <button className="primary-btn" onClick={onGoToChat}>Go to Chat</button>
        </div>
      )}

      {hasMetrics && (
        <div className="card">
          <h3>Your Numbers</h3>
          <div className="metrics">
            <Metric label="BMI" value={bmi?.bmi_value} icon="target" />
            <Metric label="Status" value={bmi?.bmi_status} icon="activity" />
            <Metric label="BMR" value={bmi?.bmr} unit=" kcal" icon="bolt" />
            <Metric label="Calories" value={macro?.daily_calories_target} unit=" kcal/day" icon="scale" />
            <Metric label="Protein" value={macro?.protein_g} unit=" g/day" icon="plate" />
            <Metric label="Carbs" value={macro?.carbs_g} unit=" g/day" icon="plate" />
            <Metric label="Fats" value={macro?.fats_g} unit=" g/day" icon="plate" />
            <Metric label="Water" value={water?.water_intake_liters} unit=" L/day" icon="drop" />
          </div>
        </div>
      )}

      {dietPlan && (
        <div className="card">
          <h3><Icon name="plate" size={16} /> Nutrition Plan</h3>
          <Report text={dietPlan} />
        </div>
      )}

      {workoutPlan && (
        <div className="card">
          <h3><Icon name="dumbbell" size={16} /> Workout Plan</h3>
          <Report text={workoutPlan} />
        </div>
      )}

      {gymData && (
        <div className="card">
          <h3><Icon name="gym" size={16} /> Gym Recommendations</h3>
          <Report text={gymData} />
        </div>
      )}
    </section>
  );
}

export default MyPlanView;
