// اعلان ساده و موقت (success یا error)
function showAlert(message, type = "success", duration = 3200) {
  const old = document.getElementById("main-alert");
  if (old) old.remove();

  const alert = document.createElement("div");
  alert.id = "main-alert";
  alert.className = (type === "error") ? "alert-error" : "alert-success";
  alert.style.position = "fixed";
  alert.style.top = "2.2rem";
  alert.style.right = "50%";
  alert.style.transform = "translateX(50%)";
  alert.style.zIndex = 9999;
  alert.textContent = message;
  document.body.appendChild(alert);

  setTimeout(() => { alert.remove(); }, duration);
}
const overlay = document.getElementById('device-overlay');

document.addEventListener("DOMContentLoaded", () => {
  const first = document.querySelector('form input:not([type=hidden]):not([disabled])');
  if (first) first.focus();
  if (overlay) {
    setTimeout(() => {
      overlay.style.opacity = '0';
      setTimeout(() => overlay.style.display = 'none', 2000);
    }, 3500);
  }
  document.querySelectorAll("[data-alert]").forEach(btn => {
    btn.addEventListener("click", e => {
      showAlert(btn.dataset.alert, btn.dataset.type || "success");
    });
  });

});
