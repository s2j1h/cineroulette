(function () {
  const readerEl = document.getElementById("reader");
  const statusEl = document.getElementById("scan-status");
  const eanForm = document.getElementById("ean-form");
  const eanInput = document.getElementById("ean-input");
  if (!readerEl || typeof Quagga === "undefined") return;

  // Un code n'est accepté qu'après avoir été lu plusieurs fois d'affilée à
  // l'identique : réduit les faux positifs (chiffre mal lu ponctuellement)
  // sans complexifier la config, technique recommandée par la doc Quagga2.
  const REQUIRED_CONSECUTIVE_MATCHES = 3;

  let scanning = true;
  let lastCode = null;
  let repeatCount = 0;

  function submitEan(decodedText) {
    eanInput.value = decodedText;
    eanForm.submit();
  }

  function onDetected(result) {
    if (!scanning || !result || !result.codeResult) return;
    if (result.codeResult.format !== "ean_13") return;

    const code = result.codeResult.code;
    if (code === lastCode) {
      repeatCount += 1;
    } else {
      lastCode = code;
      repeatCount = 1;
    }
    if (repeatCount < REQUIRED_CONSECUTIVE_MATCHES) return;

    scanning = false;
    statusEl.textContent = `Code détecté : ${code} — recherche en cours...`;
    Quagga.offDetected(onDetected);
    Quagga.offProcessed(onProcessed);
    Quagga.stop().then(() => submitEan(code)).catch(() => submitEan(code));
  }

  function onProcessed(result) {
    const ctx = Quagga.canvas && Quagga.canvas.ctx.overlay;
    const canvas = Quagga.canvas && Quagga.canvas.dom.overlay;
    if (!ctx || !canvas || !result) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (result.boxes) {
      result.boxes
        .filter((box) => box !== result.box)
        .forEach((box) => Quagga.ImageDebug.drawPath(box, { x: 0, y: 1 }, ctx, { color: "#4f7cff", lineWidth: 2 }));
    }
    if (result.box) {
      Quagga.ImageDebug.drawPath(result.box, { x: 0, y: 1 }, ctx, { color: "#3fae66", lineWidth: 2 });
    }
    if (result.codeResult && result.codeResult.code) {
      Quagga.ImageDebug.drawPath(result.line, { x: "x", y: "y" }, ctx, { color: "#c0392b", lineWidth: 3 });
    }
  }

  Quagga.init(
    {
      inputStream: {
        type: "LiveStream",
        target: readerEl,
        // Codes-barres de jaquettes souvent petits/imprimés serré : résolution
        // de traitement plus haute, cf. doc Quagga2 "Handle Difficult Barcodes".
        size: 1280,
        constraints: {
          facingMode: "environment",
          width: { ideal: 1920 },
          height: { ideal: 1080 },
        },
      },
      locator: {
        patchSize: "small",
        halfSample: true,
      },
      decoder: {
        readers: ["ean_reader"],
      },
      locate: true,
    },
    (err) => {
      if (err) {
        if (err.name === "NotFoundError") {
          statusEl.textContent = "Aucune caméra détectée sur cet appareil.";
        } else if (err.name === "NotAllowedError") {
          statusEl.textContent = "Accès caméra refusé.";
        } else {
          statusEl.textContent = "Impossible d'accéder à la caméra : " + err;
        }
        console.error(err);
        return;
      }
      Quagga.start();
    }
  );

  Quagga.onDetected(onDetected);
  Quagga.onProcessed(onProcessed);
})();
