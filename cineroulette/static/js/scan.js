(function () {
  const readerEl = document.getElementById("reader");
  const statusEl = document.getElementById("scan-status");
  const eanForm = document.getElementById("ean-form");
  const eanInput = document.getElementById("ean-input");
  if (!readerEl || typeof Html5Qrcode === "undefined") return;

  let scanning = true;

  const html5QrCode = new Html5Qrcode("reader", {
    formatsToSupport: [Html5QrcodeSupportedFormats.EAN_13],
    verbose: false,
  });

  function submitEan(decodedText) {
    eanInput.value = decodedText;
    eanForm.submit();
  }

  function onScanSuccess(decodedText) {
    if (!scanning) return;
    scanning = false;
    statusEl.textContent = `Code détecté : ${decodedText} — recherche en cours...`;
    html5QrCode.stop().then(() => submitEan(decodedText)).catch(() => submitEan(decodedText));
  }

  function onScanFailure() {
    // Pas de code détecté sur cette frame : comportement normal pendant le scan.
  }

  Html5Qrcode.getCameras()
    .then((cameras) => {
      if (!cameras || !cameras.length) {
        statusEl.textContent = "Aucune caméra détectée sur cet appareil.";
        return;
      }
      const cameraId = cameras[cameras.length - 1].id;
      html5QrCode
        .start(cameraId, { fps: 10, qrbox: { width: 280, height: 120 } }, onScanSuccess, onScanFailure)
        .catch((err) => {
          statusEl.textContent = "Impossible d'accéder à la caméra : " + err;
          console.error(err);
        });
    })
    .catch((err) => {
      statusEl.textContent = "Accès caméra refusé ou indisponible : " + err;
      console.error(err);
    });
})();
