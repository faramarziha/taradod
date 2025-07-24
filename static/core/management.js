document.addEventListener('DOMContentLoaded', () => {
  const carousel = document.querySelector('.options-carousel');
  const next = document.querySelector('.carousel-btn.next');
  const prev = document.querySelector('.carousel-btn.prev');
  if (carousel && next && prev) {
    const step = 180;
    next.addEventListener('click', () => {
      carousel.scrollBy({left: step, behavior: 'smooth'});
    });
    prev.addEventListener('click', () => {
      carousel.scrollBy({left: -step, behavior: 'smooth'});
    });
  }
});

