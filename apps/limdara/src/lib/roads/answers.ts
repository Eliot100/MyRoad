function numericValue(raw: string): number | null {
  const text = raw.replace(/\s+/g, "");
  if (/^[+-]?\d+\/[+-]?\d+$/.test(text)) {
    const [n, d] = text.split("/").map(Number);
    if (!d) return null;
    return n / d;
  }
  if (/^[+-]?\d+(\.\d+)?$/.test(text)) return Number(text);
  return null;
}

function norm(raw: string) {
  return raw
    .trim()
    .toLowerCase()
    .replace(/[−–—]/g, "-")
    .replace(/[×·]/g, "*")
    .replace(/√/g, "sqrt")
    .replace(/π/g, "pi")
    .replace(/\s+/g, "")
    .replace(/[.,;:!?]/g, "");
}

export function answersMatch(input: string, expected: string) {
  if (!input.trim() || !expected.trim()) return false;
  const left = norm(input);
  const right = norm(expected);
  if (left === right) return true;
  const a = numericValue(left);
  const b = numericValue(right);
  if (a === null || b === null) return false;
  return Math.abs(a - b) < 1e-6;
}
