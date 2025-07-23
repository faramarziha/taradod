// اعلان ساده و موقت (success یا error)
function showAlert(message, type = "success", duration = 3200) {
  const old = document.getElementById("main-alert");
  if (old) old.remove();

  const alert = document.createElement("div");
  alert.id = "main-alert";
  alert.className = ((type === "error") ? "alert-error" : "alert-success") + " fade-in";
  document.body.appendChild(alert);
  alert.textContent = message;
  setTimeout(() => alert.classList.add("fade-out"), duration - 400);
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

  const navToggle = document.getElementById("nav-toggle");
  const mainNav = document.getElementById("main-nav");
  const sidebar = document.getElementById("management-sidebar");
  const body = document.body;
  const sbOverlay = document.getElementById("sidebar-overlay");
  if (navToggle) {
    navToggle.addEventListener("click", () => {
      if (sidebar) {
        sidebar.classList.toggle("open");
        body.classList.toggle("sidebar-open");
      } else if (mainNav) {
        mainNav.classList.toggle("open");
      }
    });
  }
  if (sbOverlay && sidebar) {
    sbOverlay.addEventListener("click", () => {
      sidebar.classList.remove("open");
      body.classList.remove("sidebar-open");
    });
  }

});
