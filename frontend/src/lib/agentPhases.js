import { timeNow } from './utils.js';

// Maps the backend's SSE phase/node events to short, user-friendly labels
// and builds a timeline of steps for the current chat turn. Internal
// LangGraph node names (planner, *_worker, evaluator, replanner) are never
// shown directly in the UI.
//
// The workflow graph (see backend/graph/workflow.py) guarantees every turn
// passes: planner -> executor/worker(s) -> evaluator, optionally looping
// through replanner -> executor/worker(s) -> evaluator again. That fixed
// topology is the only thing we ever pre-render as "pending" (a hollow
// timeline item) — which worker(s) run, and how many, is never known ahead
// of time and is only added once its own "executing" event arrives.
//
// Each step carries a short `detail` caption describing what that phase
// actually does (grounded in the real tool/agent code, not invented
// telemetry). Only diet/workout/gym/general workers stream real tokens
// from the backend — for those, `detail` is live-replaced by the actual
// streamed text as it arrives (see appendStepToken below). The three
// deterministic calculator tools (bmi/water/macros) and the
// planner/evaluator/replanner phases run as a single call with no
// intermediate backend events, so their `detail` stays the static caption
// rather than a fabricated step-by-step log.
const WORKER_LABELS = {
  bmi_worker: 'Checking your profile',
  water_worker: 'Checking your profile',
  macros_worker: 'Checking your profile',
  diet_worker: 'Creating your diet plan',
  workout_worker: 'Creating your workout plan',
  gym_worker: 'Finding nearby gyms',
  general_worker: 'Preparing your answer',
};

const STREAMED_WORKERS = new Set(['diet_worker', 'workout_worker', 'gym_worker', 'general_worker']);

const STATIC_DETAIL = {
  planning: 'Reviewing your goal, your profile, and what is needed to help you.',
  bmi_worker: 'Calculating BMI, BMR, hydration, and calorie/macro targets from your profile.',
  water_worker: 'Calculating BMI, BMR, hydration, and calorie/macro targets from your profile.',
  macros_worker: 'Calculating BMI, BMR, hydration, and calorie/macro targets from your profile.',
  diet_worker: 'Writing a personalized nutrition plan based on your goal and targets…',
  workout_worker: 'Writing a personalized workout plan based on your goal and profile…',
  gym_worker: 'Looking for gyms and fitness options near your location…',
  general_worker: 'Putting together an answer to your question…',
  evaluating: 'Checking the result matches your goal before sending it back.',
  replanning: 'Adjusting the plan based on what the check found.',
};

function workerLabel(node) {
  return WORKER_LABELS[node] || 'Working on your request';
}

// `kind` identifies a step's role for lookups (e.g. "find the evaluating
// slot"); `key` is what React uses to track list identity and must stay
// unique across the whole array even when the same `kind` recurs (e.g. a
// replan cycle creates a second "evaluating" placeholder while an earlier,
// now-done one is still in the list).
function lastIndexOfKind(steps, kind) {
  for (let i = steps.length - 1; i >= 0; i -= 1) {
    if (steps[i].kind === kind) return i;
  }
  return -1;
}

// Completed steps collapse back down to just their title + checkmark — the
// expanded detail (live text or caption) only ever belongs to the step
// that's actually in progress right now.
function settleActive(steps) {
  return steps.map(s => (s.status === 'active' ? { ...s, status: 'done', detail: null, live: false } : s));
}

function makeStep(kind, label, status, node, uniq) {
  return {
    key: `${kind}-${uniq}`, kind, label, status, node: node || null,
    time: timeNow(), detail: STATIC_DETAIL[node] || STATIC_DETAIL[kind] || null, live: false,
  };
}

// Pure reducer: (current steps, SSE phase, SSE node) -> next steps.
export function advanceSteps(steps, phase, node) {
  const list = steps ? [...steps] : [];

  switch (phase) {
    case 'planning': {
      if (lastIndexOfKind(list, 'planning') === -1) {
        list.push(makeStep('planning', 'Understanding your goal', 'active', 'planning', list.length));
      }
      if (lastIndexOfKind(list, 'evaluating') === -1) {
        list.push(makeStep('evaluating', 'Evaluating your plan', 'pending', 'evaluating', list.length));
      }
      return list;
    }
    case 'executing': {
      const settled = settleActive(list);
      const evalIdx = lastIndexOfKind(settled, 'evaluating');
      const step = makeStep('exec', workerLabel(node), 'active', node, settled.length);
      if (STREAMED_WORKERS.has(node)) step.live = true;
      if (evalIdx === -1) return [...settled, step];
      return [...settled.slice(0, evalIdx), step, ...settled.slice(evalIdx)];
    }
    case 'evaluating': {
      const settled = settleActive(list);
      const idx = lastIndexOfKind(settled, 'evaluating');
      if (idx === -1) return [...settled, makeStep('evaluating', 'Evaluating your plan', 'active', 'evaluating', settled.length)];
      settled[idx] = { ...settled[idx], status: 'active', time: timeNow() };
      return settled;
    }
    case 'replanning': {
      const settled = settleActive(list);
      return [
        ...settled,
        makeStep('replanning', 'Refining the plan', 'active', 'replanning', settled.length),
        makeStep('evaluating', 'Evaluating your plan', 'pending', 'evaluating', settled.length + 1),
      ];
    }
    case 'completed':
      return list.map(s => (s.status === 'active' || s.status === 'pending' ? { ...s, status: 'done' } : s));
    default:
      return list;
  }
}

// Appends a real streamed token to the currently-active, live-streaming
// step's detail (diet/workout/gym/general only — see STREAMED_WORKERS).
export function appendStepToken(steps, token) {
  if (!steps || !steps.length) return steps;
  const idx = steps.length - 1;
  const last = steps[idx];
  if (!last.live || last.status !== 'active') return steps;
  const next = [...steps];
  next[idx] = { ...last, detail: (last.detail && last.detail !== STATIC_DETAIL[last.node] ? last.detail : '') + token };
  return next;
}

export default advanceSteps;
