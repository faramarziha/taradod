document.addEventListener('DOMContentLoaded', () => {
  const video = document.getElementById('video');
  const canvas = document.getElementById('canvas');
  const ctx = canvas.getContext('2d');
  const message = document.getElementById('message');
  const frameGuide = document.getElementById('frame-guide');
  const userInfo = document.getElementById('user-info');
  const userFace = document.getElementById('user-face');
  const userFullname = document.getElementById('user-fullname');
  const userPersonnel = document.getElementById('user-personnel');
  const userTime = document.getElementById('user-time');
  const managerControls = document.getElementById('manager-controls');
  const overlay = document.getElementById('device-overlay');

  const faceDetector = window.FaceDetector ? new FaceDetector({ fastMode: true }) : null;
  let framingOk = false;
  let verifying = false;
  let unsupportedWarned = false;
  let messageHoldUntil = 0;

  function showMessage(text, holdMs = 0) {
    message.textContent = text;
    if (holdMs > 0) {
      messageHoldUntil = Date.now() + holdMs;
    }
  }

  if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: 'user' } })
      .then((stream) => {
        video.srcObject = stream;
      })
      .catch(() => {
        showMessage('دسترسی به دوربین امکان‌پذیر نیست.');
      });
  } else {
    showMessage('دوربین توسط مرورگر پشتیبانی نمی‌شود.');
  }

  function capture() {
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.save();
    ctx.scale(-1, 1);
    ctx.drawImage(video, -canvas.width, 0, canvas.width, canvas.height);
    ctx.restore();
    return canvas.toDataURL('image/jpeg');
  }

  function showUserInfo(data) {
    userFace.src = data.image_url || '/static/core/avatar.png';
    userFullname.textContent = data.name || '';
    userPersonnel.textContent = data.code ? `کد پرسنلی: ${data.code}` : '';
    userTime.textContent = data.timestamp ? `زمان: ${new Date(data.timestamp).toLocaleTimeString('fa-IR')}` : '';
    userInfo.style.display = '';
  }

  function hideUserInfo() {
    userInfo.style.display = 'none';
  }

  async function updateFraming() {
    if (verifying || Date.now() < messageHoldUntil) return;
    if (video.readyState !== video.HAVE_ENOUGH_DATA) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.save();
    ctx.scale(-1, 1);
    ctx.drawImage(video, -canvas.width, 0, canvas.width, canvas.height);
    ctx.restore();

    let brightness = 0;
    try {
      const imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
      for (let i = 0; i < imgData.data.length; i += 40) {
        const r = imgData.data[i];
        const g = imgData.data[i + 1];
        const b = imgData.data[i + 2];
        brightness += 0.299 * r + 0.587 * g + 0.114 * b;
      }
      brightness /= imgData.data.length / 40;
    } catch (e) {

    }

    let color = 'red';
    let msg = 'لطفاً صورت خود را در کادر قرار دهید.';
    framingOk = false;

    if (brightness < 60) {
      color = 'yellow';
      msg = 'نور محیط کافی نیست.';
    } else if (faceDetector) {
      try {
        const faces = await faceDetector.detect(canvas);
        if (faces.length === 0) {
          color = 'red';
          msg = 'لطفاً صورت خود را در کادر قرار دهید.';
        } else {
          const box = faces[0].boundingBox;
          const area = (box.width * box.height) / (canvas.width * canvas.height);
          if (area < 0.1) {
            color = 'red';
            msg = 'لطفاً نزدیک‌تر شوید.';
          } else {
            color = 'green';
            msg = 'عالی! لطفاً ثابت بمانید.';
            framingOk = true;
          }
        }
      } catch (e) {
        color = 'yellow';
        msg = 'مشکل در تشخیص چهره.';
      }
    } else {
      frameGuide.style.borderColor = 'yellow';
      framingOk = true;
      if (!unsupportedWarned) {
        showMessage('راهنمای هوشمند توسط مرورگر پشتیبانی نمی‌شود.', 4000);
        unsupportedWarned = true;
      }
      return;
    }

    frameGuide.style.borderColor = color;
    showMessage(msg);
  }

  setInterval(updateFraming, 800);

  function wait(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  async function verifyLoop() {
    if (verifying || !framingOk) {
      setTimeout(verifyLoop, 1000);
      return;
    }
    verifying = true;
    showMessage('لطفاً مستقیم به دوربین نگاه کنید.');
    await wait(1000);
    const img1 = capture();
    showMessage('حالا سرتان را کمی حرکت دهید.');
    await wait(3000);
    const img2 = capture();
    showMessage('در حال بررسی...');

    fetch(VERIFY_FACE_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
      },
      body: JSON.stringify({ image1: img1, image2: img2 }),
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.ok) {
          const actionText = data.log_type === 'in' ? 'ورود' : 'خروج';
          showMessage(`تردد ${actionText} ثبت شد!`, 4000);
          showUserInfo(data);
          managerControls.style.display = 'none';
        } else if (data.manager_detected) {
          showMessage('مدیر شناسایی شد.', 4000);
          managerControls.style.display = '';
          hideUserInfo();
        } else if (data.suspicious) {
          showMessage('تشخیص مشکوک! لطفاً با مدیریت تماس بگیرید.', 4000);
          hideUserInfo();
          managerControls.style.display = 'none';
        } else {
          showMessage(
            data.msg || 'چهره‌ای شناسایی نشد. لطفاً صورت خود را مقابل دوربین تنظیم کنید.',
            4000
          );
          hideUserInfo();
          managerControls.style.display = 'none';
        }
      })
      .catch(() => {
        showMessage('اتصال به سرور برقرار نشد. لطفاً اتصال اینترنت را بررسی کنید.', 4000);
      })
      .finally(() => {
        verifying = false;
        setTimeout(verifyLoop, 4000);
      });
  }

  verifyLoop();

  if (overlay) {
    setTimeout(() => {
      overlay.style.opacity = '0';
      setTimeout(() => (overlay.style.display = 'none'), 500);
    }, 2000);
  }

  function getCsrfToken() {
    const value = '; ' + document.cookie;
    const parts = value.split('; csrftoken=');
    if (parts.length === 2) return parts.pop().split(';').shift();
    return '';
  }
});
