document.addEventListener('DOMContentLoaded', () => {
  const layout = document.querySelector('.management-layout');
  const toggleBtn = document.getElementById('sidebar-toggle');
  if (layout && toggleBtn) {
    toggleBtn.addEventListener('click', e => {
      e.stopPropagation();
      layout.classList.toggle('sidebar-open');
    });
    layout.addEventListener('click', e => {
      if (layout.classList.contains('sidebar-open') && !e.target.closest('.management-sidebar') && e.target !== toggleBtn) {
        layout.classList.remove('sidebar-open');
      }
    });
  }
});
