// Unit tests for atlas/match — run with: node --test tests/

import { test as nodeTest } from "node:test";
import { strict as assert } from "node:assert";
import { normalize, levenshtein, thresholdFor, test as match } from "../lib/match.js";

const NEIGHBORHOODS = [
  "SoHo", "NoHo", "Tribeca", "Lower East Side", "Upper East Side", "Upper West Side",
  "Chelsea", "Greenwich Village", "West Village", "East Village",
  "Williamsburg", "Bushwick", "Bedford-Stuyvesant", "DUMBO", "Brooklyn Heights",
  "Park Slope", "Crown Heights", "Bay Ridge", "Sunset Park", "Red Hook"
];

const ALIASES = {
  "SoHo":              ["soho", "south of houston"],
  "Bedford-Stuyvesant":["bed stuy", "bedstuy", "bed-stuy"],
  "Brooklyn Heights":  ["bk heights", "brooklyn hts", "bkheights"],
  "Lower East Side":   ["les", "lowereastside"],
  "Upper East Side":   ["ues"],
  "Upper West Side":   ["uws"]
};

const OPTS = { allNames: NEIGHBORHOODS, aliases: ALIASES };

nodeTest("normalize: case + whitespace + punctuation", () => {
  assert.equal(normalize("SoHo"),                  "soho");
  assert.equal(normalize("  SoHo "),               "soho");
  assert.equal(normalize("Hell's Kitchen"),        "hellskitchen");
  assert.equal(normalize("Bedford-Stuyvesant"),    "bedfordstuyvesant");
  assert.equal(normalize(null),                    "");
});

nodeTest("levenshtein: known distances", () => {
  assert.equal(levenshtein("",      "abc"), 3);
  assert.equal(levenshtein("abc",   "abc"), 0);
  assert.equal(levenshtein("kitten","sitten"), 1);
  assert.equal(levenshtein("kitten","sitting"), 3);
  assert.equal(levenshtein("noho",  "soho"), 1);
});

nodeTest("thresholdFor: length-aware brackets", () => {
  assert.equal(thresholdFor(3), 0);   // <5 -> exact only
  assert.equal(thresholdFor(4), 0);
  assert.equal(thresholdFor(5), 1);   // 5-7 -> distance 1
  assert.equal(thresholdFor(7), 1);
  assert.equal(thresholdFor(8), 2);   // >=8 -> distance 2
  assert.equal(thresholdFor(20), 2);
});

nodeTest("match: exact normalized match", () => {
  assert.equal(match("SoHo",  "SoHo", OPTS), true);
  assert.equal(match("soho",  "SoHo", OPTS), true);
  assert.equal(match("Soho ", "SoHo", OPTS), true);
});

nodeTest("match: alias resolution", () => {
  assert.equal(match("bed stuy",      "Bedford-Stuyvesant", OPTS), true);
  assert.equal(match("bedstuy",       "Bedford-Stuyvesant", OPTS), true);
  assert.equal(match("BK Heights",    "Brooklyn Heights",   OPTS), true);
  assert.equal(match("LES",           "Lower East Side",    OPTS), true);
});

nodeTest("match: alias resolves to target only — not all targets", () => {
  // 'soho' is an alias for SoHo. If target is NoHo, it should not match.
  assert.equal(match("soho", "NoHo", OPTS), false);
  // 'bed stuy' is alias for Bedford-Stuyvesant. Target Park Slope -> false.
  assert.equal(match("bed stuy", "Park Slope", OPTS), false);
});

nodeTest("match: length-aware fuzzy — accepts close spellings on long names", () => {
  // 'williamsbrg' is distance 1 from 'williamsburg' (12 chars -> threshold 2)
  assert.equal(match("williamsbrg", "Williamsburg", OPTS), true);
  // 'lowereastsde' is distance 1 from 'lowereastside' (13 chars)
  assert.equal(match("lowereastsde", "Lower East Side", OPTS), true);
});

nodeTest("match: rejects when input matches a DIFFERENT canonical name better", () => {
  // The critical NoHo/SoHo case — distance 1, but they're both real neighborhoods.
  assert.equal(match("NoHo", "SoHo", OPTS), false);
  assert.equal(match("noho", "SoHo", OPTS), false);
});

nodeTest("match: rejects too-distant inputs", () => {
  assert.equal(match("harlem", "SoHo", OPTS), false);
  assert.equal(match("queens", "Brooklyn Heights", OPTS), false);
});

nodeTest("match: short names get exact-only matching", () => {
  // SoHo is 4 chars — threshold 0
  assert.equal(match("Soho",  "SoHo", OPTS), true);   // normalizes to exact
  assert.equal(match("SoHoo", "SoHo", OPTS), false);  // 1 char different, but len < 5 means no fuzzy
  assert.equal(match("DUMBO", "DUMBO", OPTS), true);
  assert.equal(match("DUMBA", "DUMBO", OPTS), true);  // len 5 -> threshold 1, 1 edit, no other 'dumba' canonical
});

nodeTest("match: empty / whitespace input rejects", () => {
  assert.equal(match("",   "SoHo", OPTS), false);
  assert.equal(match("  ", "SoHo", OPTS), false);
});

nodeTest("match: missing options falls back to no aliases", () => {
  assert.equal(match("SoHo", "SoHo", { allNames: ["SoHo"] }), true);
  assert.equal(match("soho", "SoHo"), true); // normalizes to exact
});
