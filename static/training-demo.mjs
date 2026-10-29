import { runTraining } from './training-model.mjs';
import { fireSequence } from './training-g1-motion.mjs';

const $ = selector => document.querySelector(selector);
const number = value => value.toFixed(2);
const form = $('#training-form');
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
let currentResult = null;
let currentStep = 0;
let timer = null;
let g1View = null;
let lastAim = { prediction: 0, expected: Math.atan2(0.84, 2.7) * 180 / Math.PI, lateral: 0.84, spraying: false, fire: 1, smoke: 0, fires: [1, 1, 1], slot: 2, robotY: 0 };

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
  $('#playback-button').textContent = currentResult && currentStep === currentResult.trainingCases ? 'Replay' : 'Play';
}

function drawStep(index) {
  if (!currentResult) return;
  currentStep = Math.max(0, Math.min(index, currentResult.trainingCases));
  const step = currentResult.steps[currentStep];
  const sequence = fireSequence(currentResult.steps, currentResult.test, currentStep, Number($('#target-select').value));
  const target = currentResult.test[sequence.targetIndex];
  const prediction = step.slope * target.lateral + step.intercept;
  const { fire, smoke, spraying } = sequence;
  lastAim = { prediction, expected: target.expected, lateral: target.lateral, spraying, fire, smoke, fires: sequence.fires, slot: sequence.slot, robotY: -target.lateral * 0.55 };
  if (g1View) g1View.setAim(lastAim);
  const originX = 320, originY = 284, targetY = 44, scale = (originY - targetY) / 2.7;
  const targetX = originX + target.lateral * scale;
  const aimX = originX + Math.tan(prediction * Math.PI / 180) * (originY - targetY);
  $('#teacher-ray').setAttribute('x2', targetX);
  $('#model-ray').setAttribute('x2', aimX);
  $('#aim-point').setAttribute('cx', aimX);
  $('#model-ray').setAttribute('visibility', spraying ? 'visible' : 'hidden');
  $('#aim-point').setAttribute('visibility', spraying ? 'visible' : 'hidden');
  $('#target-marker').setAttribute('transform', `translate(${targetX} ${targetY}) translate(0 13) scale(${fire}) translate(0 -13)`);
  $('#smoke-marker').setAttribute('transform', `translate(${targetX} ${targetY})`);
  $('#smoke-marker').setAttribute('opacity', smoke);
  $('#timeline').value = String(currentStep);
  $('#timeline').setAttribute('aria-valuetext', `${currentStep} of ${currentResult.trainingCases} examples`);
  $('#step-count').textContent = `${currentStep} / ${currentResult.trainingCases} examples`;
  $('#model-angle').textContent = `${number(prediction)}°`;
  $('#teacher-angle').textContent = `${number(target.expected)}°`;
  $('#aim-error').textContent = `${number(Math.abs(prediction - target.expected))}°`;
  $('#fire-progress').textContent = `${sequence.completed} / 3 fires out · ${['Left', 'Centre', 'Right'][sequence.slot]} target`;
  $('#scene-description').textContent = `${$('#fire-progress').textContent}. Target offset ${number(target.lateral)} metres. Teacher angle ${number(target.expected)} degrees; model angle ${number(prediction)} degrees after ${currentStep} examples. Simulated fire ${fire === 0 ? 'out; spray stopped' : `${Math.round(fire * 100)} percent remaining; spray on`}.${smoke > 0 ? ' Smoke fading.' : ''}`;
  if (g1View) $('#g1-view').setAttribute('aria-label', `G1 spray and fire illustration. ${$('#scene-description').textContent}`);
}

function play() {
  if (!currentResult || timer !== null) return;
  if (currentStep >= currentResult.trainingCases) drawStep(0);
  $('#playback-button').textContent = 'Pause';
  $('#status').textContent = 'Replaying training examples';
  if (g1View) g1View.setPlayback(true);
  const delay = Math.max(55, Math.min(200, 8000 / currentResult.trainingCases));
  timer = setInterval(() => {
    drawStep(currentStep + 1);
    if (currentStep >= currentResult.trainingCases) {
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
  $('#playback-button').textContent = currentStep === currentResult.trainingCases ? 'Replay' : 'Play';
  $('#status').textContent = currentStep === currentResult.trainingCases ? 'Training complete' : 'Playback paused';
});
$('#target-select').addEventListener('change', () => drawStep(currentStep));

form.addEventListener('submit', event => {
  event.preventDefault();
  if (!form.reportValidity()) return;
  try {
    stopPlayback();
    const result = runTraining({ trainingCases: Number($('#training-cases').value), seed: Number($('#seed').value) });
    currentResult = result;
    $('#timeline').max = String(result.trainingCases);
    $('#timeline').disabled = false;
    $('#target-select').disabled = false;
    $('#playback-button').disabled = false;
    drawStep(reducedMotion.matches ? result.trainingCases : 0);
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
