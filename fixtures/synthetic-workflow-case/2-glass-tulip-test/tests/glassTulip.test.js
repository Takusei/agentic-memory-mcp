const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const root = path.resolve(__dirname, "..");

function readJson(relativePath) {
  return JSON.parse(fs.readFileSync(path.join(root, relativePath), "utf8"));
}

function filesIn(relativePath) {
  const absolutePath = path.join(root, relativePath);
  if (!fs.existsSync(absolutePath)) {
    return [];
  }
  return fs.readdirSync(absolutePath).filter((entry) => {
    return fs.statSync(path.join(absolutePath, entry)).isFile();
  });
}

test("cards are archived and renamed by internal id", () => {
  assert.deepEqual(filesIn("incoming/cards"), []);
  assert.deepEqual(filesIn("archive/cards").sort(), [
    "card-delta.json",
    "card-epsilon.json",
  ]);
  assert.equal(readJson("archive/cards/card-delta.json").title, "Delta packing note");
  assert.equal(readJson("archive/cards/card-epsilon.json").title, "Epsilon routing note");
});

test("scratch files are deleted", () => {
  assert.deepEqual(filesIn("scratch"), []);
});

test("summary report captures source analysis and archive output", () => {
  assert.deepEqual(readJson("reports/glass-tulip-summary.json"), {
    workflow: "GLASS_TULIP_ARCHIVE_V1",
    sourceName: "validation-ledger",
    sourceCount: 2,
    archivedCardIds: ["card-delta", "card-epsilon"],
    quarantinedCardIds: [],
    scratchCleared: true,
  });
});
