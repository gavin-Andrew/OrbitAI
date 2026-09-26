// Local filtering only. Selected materials remain visible and selected.
document.querySelectorAll('[data-material-filter]').forEach(input => {
  input.addEventListener('input', () => {
    const term = input.value.trim().toLocaleLowerCase();
    input.closest('form').querySelectorAll('[data-material-choice]').forEach(item => {
      item.hidden = !item.querySelector('input[type=checkbox]').checked
        && !item.dataset.search.toLocaleLowerCase().includes(term);
    });
  });
});
