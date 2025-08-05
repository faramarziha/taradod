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
  const sidebarOverlay = document.getElementById("sidebar-overlay");
  if (navToggle) {
    const icon = navToggle.querySelector("i");
    navToggle.addEventListener("click", () => {
      navToggle.classList.toggle("open");
      if (sidebar) {
        const isOpen = sidebar.classList.toggle("open");
        if (sidebarOverlay) sidebarOverlay.classList.toggle("open", isOpen);
        navToggle.setAttribute("aria-expanded", isOpen);
        if (icon) {
          icon.classList.toggle("fa-bars", !isOpen);
          icon.classList.toggle("fa-times", isOpen);
        }
      } else if (mainNav) {
        const isOpen = mainNav.classList.toggle("open");
        navToggle.setAttribute("aria-expanded", isOpen);
        if (icon) {
          icon.classList.toggle("fa-bars", !isOpen);
          icon.classList.toggle("fa-times", isOpen);
        }
      }
    });
  }
  if (sidebarOverlay) {
    sidebarOverlay.addEventListener("click", () => {
      sidebar.classList.remove("open");
      sidebarOverlay.classList.remove("open");
      if (navToggle) {
        navToggle.classList.remove("open");
        navToggle.setAttribute("aria-expanded", "false");
        const icon = navToggle.querySelector("i");
        if (icon) {
          icon.classList.add("fa-bars");
          icon.classList.remove("fa-times");
        }
      }
    });
  }

});
