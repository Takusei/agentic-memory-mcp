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

test("normal cards are archived and renamed by internal id", () => {
  assert.deepEqual(filesIn("incoming/cards"), []);
  assert.deepEqual(filesIn("archive/cards").sort(), [
    "card-alpha.json",
    "card-gamma.json",
  ]);
  assert.equal(readJson("archive/cards/card-alpha.json").title, "Alpha inventory note");
  assert.equal(readJson("archive/cards/card-gamma.json").title, "Gamma routing note");
});

test("flagged cards are quarantined and renamed by internal id", () => {
  assert.deepEqual(filesIn("archive/quarantine"), ["card-beta.json"]);
  assert.equal(readJson("archive/quarantine/card-beta.json").title, "Beta exception note");
});

test("scratch files are deleted", () => {
  assert.deepEqual(filesIn("scratch"), []);
});

test("summary report captures source analysis and archive output", () => {
  assert.deepEqual(readJson("reports/glass-tulip-summary.json"), {
    workflow: "GLASS_TULIP_ARCHIVE_V1",
    sourceName: "original-ledger",
    sourceCount: 3,
    archivedCardIds: ["card-alpha", "card-gamma"],
    quarantinedCardIds: ["card-beta"],
    scratchCleared: true,
  });
});

test("original workflow writes quarantine audit note", () => {
  const auditPath = path.join(root, "reports/glass-tulip-audit.md");
  assert.equal(fs.existsSync(auditPath), true);
  assert.match(fs.readFileSync(auditPath, "utf8"), /- quarantined card-beta: Beta exception note/);
});
