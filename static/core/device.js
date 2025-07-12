document.addEventListener('DOMContentLoaded', () => {
  const video = document.getElementById('video');
  const canvas = document.getElementById('canvas');
  const message = document.getElementById('message');
  const userInfo = document.getElementById('user-info');
  const userFace = document.getElementById('user-face');
  const userFullname = document.getElementById('user-fullname');
  const userPersonnel = document.getElementById('user-personnel');
  const userTime = document.getElementById('user-time');
  const managerControls = document.getElementById('manager-controls');
  const overlay = document.getElementById('device-overlay');

  // راه‌اندازی دوربین
  if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
  navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } })
    .then(stream => { video.srcObject = stream; })
    .catch(() => { message.textContent = "اجازه دوربین رد شد."; });
} else {
  message.textContent = "دوربین توسط مرورگر پشتیبانی نمی‌شود.";
}

  function showUserInfo(data) {
    userFace.src = data.image_url || "/static/core/avatar.png";
    userFullname.textContent = data.name || '';
    userPersonnel.textContent = data.code ? `کد پرسنلی: ${data.code}` : '';
    userTime.textContent = data.timestamp ? `زمان: ${new Date(data.timestamp).toLocaleTimeString('fa-IR')}` : '';
    userInfo.style.display = '';
  }

  function hideUserInfo() { userInfo.style.display = 'none'; }

  // ارسال تصویر هر چند ثانیه برای بررسی چهره
  setInterval(() => {
    if (video.readyState === video.HAVE_ENOUGH_DATA) {
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
      const dataUrl = canvas.toDataURL('image/jpeg');
      fetch(VERIFY_FACE_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
        body: JSON.stringify({ image: dataUrl })
      })
      .then(r => r.json())
      .then(data => {
        if (data.ok) {
          message.textContent = "تردد ثبت شد!";
          showUserInfo(data);
          managerControls.style.display = "none";
        } else if (data.manager_detected) {
          message.textContent = "مدیر شناسایی شد.";
          managerControls.style.display = "";
          hideUserInfo();
        } else {
          message.textContent = data.msg || "چهره‌ای شناسایی نشد.";
          hideUserInfo();
          managerControls.style.display = "none";
        }
      }).catch(() => {
        message.textContent = "ارتباط با سرور برقرار نشد.";
      });
    }
  }, 4000);

  if (overlay) {
    setTimeout(() => {
      overlay.style.opacity = '0';
      setTimeout(() => overlay.style.display = 'none', 500); // با توجه به duration transition در CSS (اینجا 2 ثانیه)
    }, 2000); // بعد از ۳.۵ ثانیه محو میشه
  }
  function getCsrfToken() {
    let value = "; " + document.cookie;
    let parts = value.split("; csrftoken=");
    if (parts.length === 2) return parts.pop().split(";").shift();
    return '';
  }
});
