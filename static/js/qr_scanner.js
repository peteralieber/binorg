const video = document.querySelector("#camera");
const status = document.querySelector("#scan-status");
if (!("BarcodeDetector" in window)) {
  status.textContent = "QR scanning is not supported by this browser. Open the label URL manually.";
} else {
  const detector = new BarcodeDetector({ formats: ["qr_code"] });
  navigator.mediaDevices
    .getUserMedia({ video: { facingMode: "environment" } })
    .then((stream) => {
      video.srcObject = stream;
      const scan = async () => {
        const codes = await detector.detect(video);
        if (codes[0]?.rawValue) {
          window.location.assign(codes[0].rawValue);
        } else {
          requestAnimationFrame(scan);
        }
      };
      video.addEventListener("loadeddata", scan, { once: true });
    })
    .catch(() => {
      status.textContent = "Camera access was not available.";
    });
}
