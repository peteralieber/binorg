const video = document.querySelector("#camera");
const status = document.querySelector("#scan-status");
const inputForm = document.querySelector("#scan-input-form");
const input = document.querySelector("#scan-input");

const openScannedValue = (value) => {
  const scannedValue = value.trim();
  if (scannedValue) {
    window.location.assign(scannedValue);
  }
};

inputForm.addEventListener("submit", (event) => {
  event.preventDefault();
  openScannedValue(input.value);
});

const scanWithJsQr = () => {
  if (typeof window.jsQR !== "function") {
    status.textContent = "Camera scanning is unavailable. Use a USB QR scanner instead.";
    return;
  }

  const canvas = document.createElement("canvas");
  const context = canvas.getContext("2d", { willReadFrequently: true });
  const scan = () => {
    if (!video.videoWidth || !video.videoHeight) {
      requestAnimationFrame(scan);
      return;
    }
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    const code = window.jsQR(context.getImageData(0, 0, canvas.width, canvas.height).data, canvas.width, canvas.height);
    if (code?.data) {
      openScannedValue(code.data);
    } else {
      requestAnimationFrame(scan);
    }
  };
  scan();
};

if (!navigator.mediaDevices?.getUserMedia) {
  status.textContent = "Camera access is not supported by this browser. Use a USB QR scanner.";
} else {
  navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } })
    .then((stream) => {
      video.srcObject = stream;
      if ("BarcodeDetector" in window) {
        status.textContent = "Camera ready. Point it at a QR label.";
        const detector = new BarcodeDetector({ formats: ["qr_code"] });
        const scan = async () => {
          try {
            const codes = await detector.detect(video);
            if (codes[0]?.rawValue) {
              openScannedValue(codes[0].rawValue);
            } else {
              requestAnimationFrame(scan);
            }
          } catch {
            status.textContent = "Camera scanning failed. Use a USB QR scanner instead.";
          }
        };
        video.addEventListener("loadeddata", scan, { once: true });
      } else {
        status.textContent = "Camera ready. Point it at a QR label.";
        scanWithJsQr();
      }
    })
    .catch(() => {
      status.textContent = "Camera access was not available. Use a USB QR scanner instead.";
    });
}
