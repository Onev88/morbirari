"use client";

import { useEffect, useState } from "react";

type Labels = {
  title: string;
  lead: string;
  accept: string;
  items: string[];
  emergency: string;
};

/**
 * Aviso legal como banner por sesión.
 *
 * - Aparece una vez por sesión de navegador (`sessionStorage`): al aceptar se pliega
 *   y no reaparece hasta abrir el sitio de nuevo. No es un modal — no bloquea el
 *   contenido ni la lectura, solo se apoya al pie.
 * - El texto completo sigue viviendo, siempre, en el `<details>` del footer (HTML del
 *   servidor): quien no tenga JavaScript, o ya haya aceptado, lo tiene ahí a un clic.
 *   Este banner es un recordatorio, no la única copia del aviso.
 * - No se pinta nada hasta montar: así quien ya aceptó no ve un parpadeo del banner.
 */
export function DisclaimerBanner({ labels }: { labels: Labels }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    let accepted = false;
    try {
      accepted = sessionStorage.getItem("disclaimerAccepted") === "1";
    } catch {
      /* sin almacenamiento: se muestra igualmente, es lo más prudente */
    }
    if (!accepted) setVisible(true);
  }, []);

  function accept() {
    try {
      sessionStorage.setItem("disclaimerAccepted", "1");
    } catch {
      /* aunque no persista, se oculta en esta sesión */
    }
    setVisible(false);
  }

  if (!visible) return null;

  return (
    <div className="disclaimer-banner" role="dialog" aria-label={labels.title} aria-modal="false">
      <div className="disclaimer-banner-inner">
        <div className="disclaimer-banner-body">
          <strong className="disclaimer-banner-title">{labels.title}</strong>
          <p className="disclaimer-banner-lead">{labels.lead}</p>
          <ul>
            {labels.items.map((it) => (
              <li key={it}>{it}</li>
            ))}
            <li>
              <strong>{labels.emergency}</strong>
            </li>
          </ul>
        </div>
        <button type="button" className="disclaimer-accept" onClick={accept}>
          {labels.accept}
        </button>
      </div>
    </div>
  );
}
