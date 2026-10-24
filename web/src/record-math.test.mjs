import assert from "node:assert/strict";
import test from "node:test";
import { formatSigned, summarizeRecord } from "./record-math.mjs";

test("formatSigned matches the app: plus, U+2212, unsigned zero", () => {
  assert.equal(formatSigned(1.2, 2, "u"), "+1.20u");
  assert.equal(formatSigned(-1.2, 2, "u"), "\u22121.20u");
  assert.equal(formatSigned(0, 2, "u"), "0.00u");
  assert.equal(formatSigned(0.001, 2, "u"), "0.00u");
  assert.equal(formatSigned(-0.001, 2, "u"), "0.00u");
  assert.equal(formatSigned("12.5", 2, "u"), "+12.50u");
});

test("retired models are left out; picks are wins plus losses plus pushes", () => {
  const rows = [
    {
      sport: "MLB",
      model_id: "mlb_f5_moneyline",
      picks: 3,
      wins: 2,
      losses: 1,
      pushes: 0,
      units: 1.5,
      risked: 3,
    },
    {
      sport: "MLB",
      model_id: "golf_make_cut",
      picks: 10,
      wins: 10,
      losses: 0,
      pushes: 0,
      units: 50,
      risked: 10,
    },
    {
      sport: "NFL",
      model_id: "nfl_spread",
      picks: 0,
      wins: 0,
      losses: 0,
      pushes: 0,
      units: 0,
      risked: 0,
    },
    {
      sport: "NBA",
      model_id: "nba_live_total",
      picks: 4,
      wins: 1,
      losses: 2,
      pushes: 1,
      units: -0.5,
      risked: 4,
    },
  ];
  const summary = summarizeRecord(rows, ["golf_make_cut"]);
  assert.ok(summary);
  assert.equal(summary.picks, 2 + 1 + 1 + 2 + 1);
  assert.equal(summary.sports, 2);
  assert.equal(summary.unitsText, "+1.00u");
});

test("nothing to show hides the row", () => {
  assert.equal(summarizeRecord([], []), null);
  assert.equal(
    summarizeRecord(
      [
        {
          sport: "MLB",
          model_id: "m",
          picks: 1,
          wins: 1,
          losses: 0,
          pushes: 0,
          units: null,
          risked: null,
        },
      ],
      [],
    ),
    null,
  );
  assert.equal(
    summarizeRecord(
      [
        {
          sport: "MLB",
          model_id: "golf_make_cut",
          picks: 4,
          wins: 4,
          losses: 0,
          pushes: 0,
          units: 3,
          risked: 4,
        },
      ],
      ["golf_make_cut"],
    ),
    null,
  );
});
