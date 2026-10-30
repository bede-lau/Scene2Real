import { runTraining } from './training-model.mjs';
import { fireSequence, replayLength } from './training-g1-motion.mjs';

const $ = selector => document.querySelector(selector);
const number = value => value.toFixed(2);
const form = $('#training-form');
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
let currentResult = null;
let currentStep = 0;
let timer = null;
let g1View = null;
let wasReturned = false;
let lastAim = { prediction: 0, expected: Math.atan2(0.84, 2.7) * 180 / Math.PI, lateral: 0.84, spraying: false, aiming: false, fire: 1, smoke: 0, fires: [1, 1, 1], slot: 2, robotY: -0.462, walkProgress: 0, walkHeading: 0, walkDistance: 0.462, lookHeading: 0 };

if (typeof window !== 'undefined') {
  const host = $('#g1-view');
  host.hidden = false;
  import('./training-g1.mjs').then(module => module.createG1View(host, { reducedMotion: reducedMotion.matches }))
    .then(view => {
      g1View = view; $('#g1-fallback').setAttribute('hidden', ''); $('#g1-status').hidden = true;
      view.setAim(lastAim); view.setPlayback(timer !== null);
    }).catch(() => {
      host.hidden = true; $('#g1-status').textContent = '3D view unavailable; showing the 2D aiming diagram.';
    });
}

function stopPlayback() {
  if (timer !== null) clearInterval(timer);
  timer = null;
  if (g1View) g1View.setPlayback(false);
  $('#playback-button').textContent = currentResult && currentStep === Number($('#timeline').max) ? 'Replay' : 'Play';
}

function drawStep(index) {
  if (!currentResult) return;
  currentStep = Math.max(0, Math.min(index, Number($('#timeline').max)));
  const examplesSeen = Math.min(currentStep, currentResult.trainingCases);
  const step = currentResult.steps[examplesSeen];
  const sequence = fireSequence(currentResult.steps, currentResult.test, currentStep, Number($('#target-select').value));
  const success = $('#return-success');
  success.hidden = !sequence.returned;
  if (sequence.returned !== wasReturned) {
    const animate = sequence.returned && timer !== null && !reducedMotion.matches;
    success.setAttribute('class', `success-badge${animate ? ' celebrate' : ''}`);
    wasReturned = sequence.returned;
  }
  const target = currentResult.test[sequence.targetIndex];
  const prediction = step.slope * target.lateral + step.intercept;
  const { fire, smoke, spraying, aiming } = sequence;
  lastAim = { prediction, expected: target.expected, lateral: target.lateral, spraying, aiming, fire, smoke, fires: sequence.fires, slot: sequence.slot, robotY: sequence.robotY, walkProgress: sequence.walkProgress, walkHeading: sequence.walkHeading, walkDistance: sequence.walkDistance, lookHeading: sequence.lookHeading };
  if (g1View) g1View.setAim(lastAim);
  const originX = 320, originY = 284, targetY = 44, scale = (originY - targetY) / 2.7;
  const targetX = originX + target.lateral * scale;
  const aimX = originX + Math.tan(prediction * Math.PI / 180) * (originY - targetY);
  $('#teacher-ray').setAttribute('x2', targetX);
  $('#model-ray').setAttribute('x2', aimX);
  $('#aim-point').setAttribute('cx', aimX);
  $('#model-ray').setAttribute('visibility', spraying ? 'visible' : 'hidden');
  $('#aim-point').setAttribute('visibility', spraying || aiming ? 'visible' : 'hidden');
  $('#target-marker').setAttribute('transform', `translate(${targetX} ${targetY}) translate(0 13) scale(${fire}) translate(0 -13)`);
  $('#smoke-marker').setAttribute('transform', `translate(${targetX} ${targetY})`);
  $('#smoke-marker').setAttribute('opacity', smoke);
  $('#timeline').value = String(currentStep);
  $('#timeline').setAttribute('aria-valuetext', `${examplesSeen} of ${currentResult.trainingCases} examples${sequence.returning ? '; returning to start' : sequence.returned ? '; returned to start' : ''}`);
  $('#step-count').textContent = `${examplesSeen} / ${currentResult.trainingCases} examples`;
  $('#model-angle').textContent = `${number(prediction)}°`;
  $('#teacher-angle').textContent = `${number(target.expected)}°`;
  $('#aim-error').textContent = `${number(Math.abs(prediction - target.expected))}°`;
  const nextName = ['left', 'centre', 'right'][sequence.nextSlot];
  $('#fire-progress').textContent = `${sequence.completed} / 3 fires out · ${sequence.returned ? 'Returned to start' : sequence.returning ? 'Returning to start' : sequence.looking ? `Looking toward ${nextName} fire` : sequence.walking ? `Walking to ${nextName} fire` : aiming ? `Aiming at ${['left', 'centre', 'right'][sequence.slot]} fire` : `${['Left', 'Centre', 'Right'][sequence.slot]} target`}`;
  $('#scene-description').textContent = `${$('#fire-progress').textContent}. Target offset ${number(target.lateral)} metres. Teacher angle ${number(target.expected)} degrees; model angle ${number(prediction)} degrees after ${examplesSeen} examples. Simulated fire ${fire === 0 ? 'out; spray stopped' : `${Math.round(fire * 100)} percent remaining; ${aiming ? 'aiming with spray off' : 'spray on'}`}.${smoke > 0 ? ' Smoke fading.' : ''}`;
  if (g1View) $('#g1-view').setAttribute('aria-label', `G1 spray and fire illustration. ${$('#scene-description').textContent}`);
}

function play() {
  if (!currentResult || timer !== null) return;
  if (currentStep >= Number($('#timeline').max)) drawStep(0);
  $('#playback-button').textContent = 'Pause';
  $('#status').textContent = 'Replaying training examples';
  if (g1View) g1View.setPlayback(true);
  const delay = Math.max(55, Math.min(200, 8000 / currentResult.trainingCases));
  let nextWalkStepAt = 0;
  timer = setInterval(() => {
    if (performance.now() < nextWalkStepAt) return;
    drawStep(currentStep + 1);
    // Keep the glance, gait and aiming pause visible for large training sets.
    if (lastAim.aiming) nextWalkStepAt = performance.now() + 600;
    else if (lastAim.walkHeading !== 0 || lastAim.lookHeading !== 0) nextWalkStepAt = performance.now() + 200;
    if (currentStep >= Number($('#timeline').max)) {
      stopPlayback();
      $('#status').textContent = 'Training complete';
    }
  }, delay);
}

$('#playback-button').addEventListener('click', () => {
  if (timer !== null) { stopPlayback(); $('#status').textContent = 'Playback paused'; }
  else play();
});
$('#timeline').addEventListener('input', event => {
  stopPlayback(); drawStep(Number(event.target.value));
  $('#playback-button').textContent = currentStep === Number($('#timeline').max) ? 'Replay' : 'Play';
  $('#status').textContent = currentStep === Number($('#timeline').max) ? 'Training complete' : 'Playback paused';
});
$('#target-select').addEventListener('change', () => {
  if (!currentResult) return;
  $('#timeline').max = String(replayLength(currentResult.steps, currentResult.test, Number($('#target-select').value)));
  drawStep(currentStep);
});

form.addEventListener('submit', event => {
  event.preventDefault();
  if (!form.reportValidity()) return;
  try {
    stopPlayback();
    const result = runTraining({ trainingCases: Number($('#training-cases').value), seed: Number($('#seed').value) });
    currentResult = result;
    $('#timeline').max = String(replayLength(result.steps, result.test, Number($('#target-select').value)));
    $('#timeline').disabled = false;
    $('#target-select').disabled = false;
    $('#playback-button').disabled = false;
    drawStep(reducedMotion.matches ? Number($('#timeline').max) : 0);
    $('#sample-count').textContent = String(result.trainingCases);
    $('#test-count').textContent = String(result.test.length);
    $('#baseline-error').textContent = `${number(result.baselineMean)}°`;
    $('#learned-error').textContent = `${number(result.learnedMean)}°`;
    $('#coefficient').textContent = `${number(result.slope)}° / m`;
    const rows = $('#case-rows');
    rows.replaceChildren();
    for (const row of result.test) {
      const tr = document.createElement('tr');
      for (const value of [`${number(row.lateral)} m`, `${number(row.expected)}°`, `${number(row.prediction)}°`, `${number(row.learnedError)}°`]) {
        const td = document.createElement('td'); td.textContent = value; tr.append(td);
      }
      rows.append(tr);
    }
    $('#results').hidden = false;
    $('#error').hidden = true;
    $('#simulation').scrollIntoView({ behavior: reducedMotion.matches ? 'auto' : 'smooth', block: 'start' });
    if (reducedMotion.matches) { $('#status').textContent = 'Training complete'; stopPlayback(); }
    else play();
  } catch (error) {
    $('#error').textContent = error.message;
    $('#error').hidden = false;
  }
});
