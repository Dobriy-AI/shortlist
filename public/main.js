document.documentElement.classList.add('js');

const menuButton = document.querySelector('.menu-toggle');
const navigation = document.querySelector('#main-nav');
const narrowScreen = window.matchMedia('(max-width: 600px)');
const closeMenu = (restoreFocus = false) => {
  navigation.classList.remove('is-open');
  menuButton.setAttribute('aria-expanded', 'false');
  if (restoreFocus) menuButton.focus();
};
const updateMenu = () => { menuButton.hidden = !narrowScreen.matches; closeMenu(); };
updateMenu();
narrowScreen.addEventListener('change', updateMenu);
menuButton.addEventListener('click', () => {
  const expanded = menuButton.getAttribute('aria-expanded') !== 'true';
  menuButton.setAttribute('aria-expanded', String(expanded));
  navigation.classList.toggle('is-open', expanded);
});
navigation.addEventListener('click', (event) => {
  if (event.target.closest('a')) closeMenu();
});
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && menuButton.getAttribute('aria-expanded') === 'true') closeMenu(true);
});
document.addEventListener('click', (event) => {
  if (!event.target.closest('.du-site-header') && menuButton.getAttribute('aria-expanded') === 'true') closeMenu();
});

const controls = document.querySelector('.source-controls');
const search = document.querySelector('#source-search');
const categories = [...document.querySelectorAll('input[name="category"]')];
const cards = [...document.querySelectorAll('.source-card')];
const count = document.querySelector('.source-count');
const empty = document.querySelector('.empty-state');
const normalize = (text) => text.normalize('NFKD').replace(/\p{Diacritic}/gu, '').toLowerCase();
const indexed = cards.map((card) => ({ card, text: normalize(card.textContent), categories: card.dataset.categories.split(' ') }));

function filterSources() {
  const query = normalize(search.value.trim()).split(/\s+/).filter(Boolean);
  const category = categories.find((input) => input.checked).value;
  let matches = 0;
  for (const source of indexed) {
    const visible = (category === 'all' || source.categories.includes(category)) && query.every((term) => source.text.includes(term));
    source.card.hidden = !visible;
    if (visible) matches++;
  }
  count.textContent = `${matches} funding ${matches === 1 ? 'source' : 'sources'}${query.length || category !== 'all' ? ' found' : ''}`;
  empty.hidden = matches !== 0;
}
controls.hidden = false;
search.addEventListener('input', filterSources);
categories.forEach((input) => input.addEventListener('change', filterSources));
document.querySelector('#reset-filters').addEventListener('click', () => {
  search.value = '';
  categories.find((input) => input.value === 'all').checked = true;
  filterSources();
  search.focus();
});
window.addEventListener('pageshow', filterSources);
