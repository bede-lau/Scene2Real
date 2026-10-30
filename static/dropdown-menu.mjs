const chevron = () => {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('class', 'dropdown-chevron');
  svg.setAttribute('viewBox', '0 0 16 16');
  svg.setAttribute('aria-hidden', 'true');
  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('d', 'm4 6 4 4 4-4');
  path.setAttribute('fill', 'none');
  path.setAttribute('stroke', 'currentColor');
  path.setAttribute('stroke-width', '1.5');
  path.setAttribute('stroke-linecap', 'round');
  path.setAttribute('stroke-linejoin', 'round');
  svg.append(path);
  return svg;
};

const check = () => {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('class', 'dropdown-check');
  svg.setAttribute('viewBox', '0 0 16 16');
  svg.setAttribute('aria-hidden', 'true');
  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('d', 'm3.5 8 2.8 2.8L12.5 4.8');
  svg.append(path);
  return svg;
};

let id = 0;
const nextId = prefix => `${prefix}-${++id}`;

function close(menu) {
  menu.dataset.open = 'false';
  menu.querySelector('.dropdown-trigger')?.setAttribute('aria-expanded', 'false');
  menu.querySelector('.dropdown-content')?.setAttribute('hidden', '');
}

function open(menu, focus = 'none') {
  const trigger = menu.querySelector('.dropdown-trigger');
  if (trigger.disabled) return;
  menu.dataset.open = 'true';
  trigger.setAttribute('aria-expanded', 'true');
  const content = menu.querySelector('.dropdown-content');
  content.removeAttribute('hidden');
  const options = [...content.querySelectorAll('[role="menuitemradio"], [role="menuitem"]')].filter(option => !option.disabled);
  if (focus === 'first') options[0]?.focus();
  if (focus === 'last') options.at(-1)?.focus();
}

function focusOption(menu, current, delta) {
  const options = [...menu.querySelectorAll('[role="menuitemradio"], [role="menuitem"]')].filter(option => !option.disabled);
  const index = Math.max(0, options.indexOf(current));
  options[(index + delta + options.length) % options.length]?.focus();
}

function wireMenu(menu) {
  const trigger = menu.querySelector('.dropdown-trigger');
  const content = menu.querySelector('.dropdown-content');
  const toggleFromTrigger = () => menu.dataset.open === 'true' ? close(menu) : open(menu, 'first');
  trigger.addEventListener('click', toggleFromTrigger);
  trigger.addEventListener('keydown', event => {
    if (event.key === 'ArrowDown') { event.preventDefault(); open(menu, 'first'); }
    if (event.key === 'ArrowUp') { event.preventDefault(); open(menu, 'last'); }
    if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); toggleFromTrigger(); }
    if (event.key === 'Escape') close(menu);
  });
  content.addEventListener('click', event => {
    if (event.target.closest?.('a.workspace-option')) close(menu);
  });
  content.addEventListener('keydown', event => {
    const active = document.activeElement;
    if (event.key === 'ArrowDown') { event.preventDefault(); focusOption(menu, active, 1); }
    if (event.key === 'ArrowUp') { event.preventDefault(); focusOption(menu, active, -1); }
    if (event.key === 'Home') { event.preventDefault(); open(menu, 'first'); }
    if (event.key === 'End') { event.preventDefault(); open(menu, 'last'); }
    if (event.key === 'Escape') { event.preventDefault(); close(menu); trigger.focus(); }
  });
  document.addEventListener('pointerdown', event => { if (!menu.contains(event.target)) close(menu); });
  document.addEventListener('focusin', event => { if (!menu.contains(event.target)) close(menu); });
}

export function upgradeSelect(select) {
  if (select.dataset.dropdownReady === 'true') return select.nextElementSibling;
  select.dataset.dropdownReady = 'true';
  const label = select.dataset.dropdownLabel || select.getAttribute('aria-label') || 'Choose an option';
  const menuId = nextId('dropdown-menu');
  const menu = document.createElement('div');
  menu.className = 'dropdown-menu';
  menu.dataset.open = 'false';
  const trigger = document.createElement('button');
  trigger.type = 'button';
  trigger.className = 'dropdown-trigger';
  trigger.setAttribute('aria-label', label);
  trigger.setAttribute('aria-haspopup', 'menu');
  trigger.setAttribute('aria-expanded', 'false');
  trigger.setAttribute('aria-controls', menuId);
  const value = document.createElement('span');
  value.className = 'dropdown-value';
  trigger.append(value, chevron());
  const content = document.createElement('div');
  content.className = 'dropdown-content';
  content.id = menuId;
  content.setAttribute('role', 'menu');
  content.setAttribute('aria-label', label);
  content.setAttribute('hidden', '');
  menu.append(trigger, content);
  select.classList.add('dropdown-native');
  select.setAttribute('aria-hidden', 'true');
  select.tabIndex = -1;
  select.insertAdjacentElement('afterend', menu);

  const render = () => {
    const options = [...select.options];
    const selected = options.find(option => option.value === select.value) || options.find(option => option.selected) || options[0];
    value.textContent = selected?.textContent || 'No options';
    trigger.disabled = select.disabled || !options.length;
    content.replaceChildren(...options.map(option => {
      const item = document.createElement('button');
      item.type = 'button';
      item.className = 'dropdown-option';
      item.setAttribute('role', 'menuitemradio');
      item.setAttribute('aria-checked', String(option.value === select.value));
      item.disabled = option.disabled;
      const marker = option.value === select.value ? check() : document.createElement('span');
      marker.classList.add('dropdown-check-spacer');
      item.append(document.createTextNode(option.textContent), marker);
      item.addEventListener('click', event => {
        event.preventDefault();
        event.stopPropagation();
        if (option.disabled) return;
        select.value = option.value;
        select.dispatchEvent(new Event('change', { bubbles: true }));
        close(menu);
        trigger.focus();
      });
      return item;
    }));
  };
  render();
  select.addEventListener('change', render);
  const ownerLabel = select.closest('label');
  ownerLabel?.addEventListener('click', event => {
    if (menu.contains(event.target) || event.target === select) return;
    event.preventDefault();
    trigger.focus();
    open(menu);
  });
  new MutationObserver(render).observe(select, { childList: true, subtree: true, attributes: true, attributeFilter: ['disabled', 'selected', 'label'] });
  wireMenu(menu);
  return menu;
}

export function upgradeSelects(root = document) {
  root?.querySelectorAll?.('select[data-dropdown-menu]').forEach(upgradeSelect);
}

export function upgradeWorkspaceMenus(root = document) {
  root?.querySelectorAll?.('[data-workspace-menu]').forEach(menu => {
    if (menu.dataset.dropdownReady === 'true') return;
    menu.dataset.dropdownReady = 'true';
    const trigger = menu.querySelector('.dropdown-trigger');
    const content = menu.querySelector('.dropdown-content');
    const menuId = nextId('workspace-menu');
    content.id = menuId;
    trigger.setAttribute('aria-controls', menuId);
    wireMenu(menu);
  });
}
