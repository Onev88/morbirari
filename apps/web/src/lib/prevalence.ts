/**
 * Traduce la clase de prevalencia de Orphanet a «1 de cada N personas».
 *
 * Orphanet publica la prevalencia como una clase textual — «1-5 / 10 000»,
 * «<1 / 1 000 000», «>1 / 1000» — que es precisa pero ilegible para quien no está
 * acostumbrado a leer tasas. Aquí se convierte a la forma que casi todo el mundo
 * entiende a la primera: «aproximadamente 1 de cada 3.000 personas».
 *
 * La cifra registrada exacta se sigue mostrando aparte: esto es una ayuda de lectura,
 * no un reemplazo. Por eso el resultado es aproximado (se marca con «≈» en la UI) y se
 * redondea a una cifra significativa: dar «1 de cada 3.333» fingiría una precisión que
 * el intervalo original no tiene.
 */

export type PlainPrevalence = {
  kind: "about" | "more" | "less";
  /** Denominador redondeado: «1 de cada {per}». */
  per: number;
};

/** Redondea a una cifra significativa (3.333 → 3.000, 1.333 → 1.000). */
function niceRound(x: number): number {
  if (x <= 0) return 0;
  const mag = 10 ** Math.floor(Math.log10(x));
  return Math.round(x / mag) * mag;
}

export function parsePrevalenceClass(cls: string | null): PlainPrevalence | null {
  if (!cls) return null;

  // Prefijo opcional (< o >), numerador (entero o rango a-b), «/», denominador (con
  // espacios/puntos como separador de millares).
  const m = cls.match(/([<>]?)\s*(\d+)\s*(?:-\s*(\d+))?\s*\/\s*([\d\s.,]+)/);
  if (!m) return null;

  const prefix = m[1];
  const a = Number(m[2]);
  const b = m[3] ? Number(m[3]) : null;
  const denom = Number(m[4].replace(/[\s.,]/g, ""));
  if (!denom || !Number.isFinite(denom)) return null;

  // «<1 / D» y «>1 / D» describen un umbral, no un punto: se conservan como tales.
  if (prefix === "<") return { kind: "less", per: denom };
  if (prefix === ">") return { kind: "more", per: denom };

  const mid = b !== null ? (a + b) / 2 : a;
  if (mid <= 0) return null;
  const per = niceRound(denom / mid);
  if (per < 1) return null;

  return { kind: "about", per };
}
