document.querySelectorAll('.flip-card').forEach((card) => {
  card.addEventListener('click', () => {
    card.classList.toggle('flipped');
  });
});

const checkoutForm = document.querySelector('#checkout-form');
if (checkoutForm) {
  checkoutForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const formData = new FormData(checkoutForm);
    const response = await fetch('/create-checkout-session', {
      method: 'POST',
      body: formData,
    });
    const payload = await response.json();
    const errorNode = document.querySelector('#checkout-error');
    if (payload.url) {
      window.location.assign(payload.url);
    } else {
      errorNode.textContent = payload.error || 'Checkout unavailable.';
    }
  });
}
