document.addEventListener("DOMContentLoaded", () => {
  const formShell = document.querySelector("[data-question-form]");
  if (!formShell) return;

  const catalog = JSON.parse(formShell.dataset.courseCatalog);
  const periodoSelect = formShell.querySelector("[data-course-select]");
  const disciplineSelect = formShell.querySelector("[data-discipline-select]");

  const renderDisciplines = () => {
    const periodo = periodoSelect.value;
    const disciplines = catalog[periodo] || [];
    disciplineSelect.innerHTML = disciplines
      .map((d) => `<option value="${d}">${d}</option>`)
      .join("");
  };

  periodoSelect.addEventListener("change", renderDisciplines);
  renderDisciplines();
});

// (user menu removed) avatar next to menu was removed; hamburger holds profile actions

// Menu hambúrguer: mesma lógica do menu de usuário
document.addEventListener("DOMContentLoaded", () => {
  const ham = document.querySelector('[data-hamburger]');
  if (!ham) return;
  const button = ham.querySelector('.hamburger-button');
  const dropdown = ham.querySelector('.hamburger-dropdown');

  if (!button || !dropdown) return;

  const close = () => {
    dropdown.classList.remove('open');
    button.setAttribute('aria-expanded', 'false');
  };

  const open = () => {
    // Posiciona o dropdown logo abaixo do botão no mobile
    if (window.innerWidth <= 700) {
      const rect = button.getBoundingClientRect();
      dropdown.style.top = (rect.bottom + 8) + 'px';
      dropdown.style.left = '12px';
      dropdown.style.right = '12px';
      dropdown.style.width = 'auto';
    } else {
      dropdown.style.top = '';
      dropdown.style.left = '';
      dropdown.style.right = '';
      dropdown.style.width = '';
    }
    dropdown.classList.add('open');
    button.setAttribute('aria-expanded', 'true');
  };

  button.addEventListener('click', (e) => {
    e.stopPropagation();
    if (dropdown.classList.contains('open')) close(); else open();
  });

  document.addEventListener('click', (e) => {
    if (!ham.contains(e.target)) close();
  });
});