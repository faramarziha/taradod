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
  const guide = document.getElementById('framing-guide');
  const guideMsg = document.getElementById('guide-message');
  const challengeBox = document.getElementById('challenge');

  if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
    navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } })
      .then(stream => { video.srcObject = stream; })
      .catch(() => { message.textContent = "دسترسی به دوربین رد شد. لطفاً اجازه دسترسی را بررسی کنید."; });
  } else {
    message.textContent = "مرورگر امکان دسترسی به دوربین را ندارد.";
  }

  function showUserInfo(data) {
    userFace.src = data.image_url || "/static/core/avatar.png";
    userFullname.textContent = data.name || '';
    userPersonnel.textContent = data.code ? `کد پرسنلی: ${data.code}` : '';
    userTime.textContent = data.timestamp ? `زمان: ${new Date(data.timestamp).toLocaleTimeString('fa-IR')}` : '';
    userInfo.style.display = '';
  }

  function hideUserInfo() { userInfo.style.display = 'none'; }

  function setGuide(color, text) {
    guide.style.borderColor = color;
    guideMsg.textContent = text;
  }

  async function analyzeFrame() {
    if (video.readyState !== video.HAVE_ENOUGH_DATA) return;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
    let sum = 0;
    for (let i = 0; i < data.length; i += 4) sum += data[i] + data[i + 1] + data[i + 2];
    const brightness = sum / (data.length / 4 * 3 * 255);

    if ('FaceDetector' in window) {
      try {
        const detector = new FaceDetector();
        const faces = await detector.detect(canvas);
        if (!faces.length) {
          setGuide('red', 'لطفاً صورت خود را مقابل دوربین قرار دهید.');
          return;
        }
        const face = faces[0].boundingBox;
        const ratio = (face.width * face.height) / (canvas.width * canvas.height);
        if (ratio < 0.1) setGuide('red', 'لطفاً نزدیک‌تر شوید.');
        else if (brightness < 0.3) setGuide('yellow', 'نور محیط کافی نیست.');
        else setGuide('green', 'عالی! لطفاً ثابت بمانید.');
      } catch (e) {
        if (brightness < 0.3) setGuide('yellow', 'نور محیط کافی نیست.');
        else setGuide('green', 'لطفاً ثابت بمانید.');
      }
    } else {
      if (brightness < 0.3) setGuide('yellow', 'نور محیط کافی نیست.');
      else setGuide('green', 'لطفاً ثابت بمانید.');
    }
  }
  setInterval(analyzeFrame, 1000);

  const challenges = ['کمی لبخند بزنید', 'سرتان را به چپ بچرخانید', 'سرتان را به راست بچرخانید'];
  let busy = false;

  async function runChallenge() {
    if (video.readyState !== video.HAVE_ENOUGH_DATA) return;
    busy = true;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const img1 = canvas.toDataURL('image/jpeg');
    const challenge = challenges[Math.floor(Math.random() * challenges.length)];
    challengeBox.style.display = '';
    challengeBox.textContent = challenge;
    await new Promise(r => setTimeout(r, 1500));
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const img2 = canvas.toDataURL('image/jpeg');
    challengeBox.style.display = 'none';
    fetch(VERIFY_FACE_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrfToken() },
      body: JSON.stringify({ challenge, image1: img1, image2: img2 })
    })
      .then(r => r.json())
      .then(data => {
        if (data.ok) {
          const actionText = data.log_type === 'in' ? 'ورود' : 'خروج';
          message.textContent = `تردد ${actionText} ثبت شد!`;
          showUserInfo(data);
          managerControls.style.display = "none";
        } else if (data.manager_detected) {
          message.textContent = "مدیر شناسایی شد.";
          managerControls.style.display = "";
          hideUserInfo();
        } else if (data.suspicious) {
          message.textContent = "تشخیص مشکوک! لطفاً با مدیریت تماس بگیرید.";
          hideUserInfo();
          managerControls.style.display = "none";
        } else {
          message.textContent = data.msg || "چهره شناسایی نشد. لطفاً کادر را تنظیم کنید.";
          hideUserInfo();
          managerControls.style.display = "none";
        }
      })
      .catch(() => {
        message.textContent = "ارتباط با سرور برقرار نشد. لطفاً اتصال اینترنت دستگاه را بررسی کنید.";
      })
      .finally(() => { busy = false; });
  }

  setInterval(() => { if (!busy) runChallenge(); }, 7000);

  function getCsrfToken() {
    let value = "; " + document.cookie;
    let parts = value.split("; csrftoken=");
    if (parts.length === 2) return parts.pop().split(";").shift();
    return '';
  }
});

