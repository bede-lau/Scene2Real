import { runTraining } from './training-model.mjs';

const $ = selector => document.querySelector(selector);
const number = value => value.toFixed(2);
const form = $('#training-form');
form.addEventListener('submit', event => {
  event.preventDefault();
  if (!form.reportValidity()) return;
  try {
    const result = runTraining({ trainingCases: Number($('#training-cases').value), seed: Number($('#seed').value) });
    $('#status').textContent = 'Training complete';
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
    $('#results').scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
  } catch (error) {
    $('#error').textContent = error.message;
    $('#error').hidden = false;
  }
});
