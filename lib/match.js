// atlas/match — fuzzy matcher (length-aware Levenshtein + aliases)
//
// Exported as ES module for unit tests; also injected into index.html
// by scripts/build_data.py (the build strips the `export` keywords).

export function normalize(s) {
  if (s == null) return "";
  return String(s)
    .toLowerCase()
    .normalize("NFD").replace(/[̀-ͯ]/g, "")
    .replace(/['’`]/g, "")
    .replace(/[^a-z0-9]+/g, "")
    .trim();
}

export function levenshtein(a, b) {
  if (a === b) return 0;
  if (!a.length) return b.length;
  if (!b.length) return a.length;
  const m = a.length, n = b.length;
  let prev = new Array(n + 1);
  let curr = new Array(n + 1);
  for (let j = 0; j <= n; j++) prev[j] = j;
  for (let i = 1; i <= m; i++) {
    curr[0] = i;
    for (let j = 1; j <= n; j++) {
      const cost = a.charCodeAt(i - 1) === b.charCodeAt(j - 1) ? 0 : 1;
      curr[j] = Math.min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost);
    }
    [prev, curr] = [curr, prev];
  }
  return prev[n];
}

export function thresholdFor(len) {
  if (len < 5) return 0;       // exact only for short names
  if (len < 8) return 1;       // 1 edit for medium
  return 2;                    // 2 edits for long
}

// Build a normalized lookup once. All canonical names + their aliases.
let _lookup = null;

export function _resetLookup() { _lookup = null; }

function _ensureLookup(allNames, aliases) {
  if (_lookup) return _lookup;
  const nameToCanonical = new Map();
  for (const canonical of allNames) {
    nameToCanonical.set(normalize(canonical), canonical);
  }
  for (const [canonical, list] of Object.entries(aliases || {})) {
    for (const a of list) {
      nameToCanonical.set(normalize(a), canonical);
    }
  }
  _lookup = nameToCanonical;
  return _lookup;
}

export function test(input, target, opts) {
  const allNames = (opts && opts.allNames) || [];
  const aliases = (opts && opts.aliases) || {};
  // Reset lookup if the caller provided a different set
  _lookup = null;
  const lookup = _ensureLookup(allNames, aliases);

  const inN = normalize(input);
  const tgtN = normalize(target);
  if (!inN) return false;

  // 1. exact normalized match against target
  if (inN === tgtN) return true;
  // 2. alias / canonical exact match — but ONLY if it resolves to the target
  if (lookup.has(inN)) {
    return normalize(lookup.get(inN)) === tgtN;
  }
  // 3. length-aware fuzzy match against target only.
  const t = thresholdFor(tgtN.length);
  if (t === 0) return false;
  const dist = levenshtein(inN, tgtN);
  if (dist > t) return false;
  // Make sure no other canonical name is closer (or as close) — guards
  // against `noho` accepting for `soho`.
  for (const [otherN /*, _canon */] of lookup) {
    if (otherN === tgtN) continue;
    const d2 = levenshtein(inN, otherN);
    if (d2 <= dist) return false;
  }
  return true;
}
