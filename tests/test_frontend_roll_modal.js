const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const { createRollModalLifecycle } = require(path.join(__dirname, "..", "frontend", "game_ui_helpers.js"));
const scriptPath = path.join(__dirname, "..", "frontend", "script.js");

function createFakeTimers() {
  const timers = new Map();
  let nextId = 1;

  return {
    setTimeout(fn) {
      const id = nextId++;
      timers.set(id, fn);
      return id;
    },
    clearTimeout(id) {
      timers.delete(id);
    },
    run(id) {
      const fn = timers.get(id);
      if (!fn) {
        return false;
      }

      timers.delete(id);
      fn();
      return true;
    },
    ids() {
      return [...timers.keys()];
    },
  };
}

test("fecha o modal mesmo depois que a rolagem já saiu do estado de rolling", () => {
  const fakeTimers = createFakeTimers();
  const closed = [];
  const lifecycle = createRollModalLifecycle({
    onClose: () => closed.push("closed"),
    setTimeoutFn: (fn) => fakeTimers.setTimeout(fn),
    clearTimeoutFn: (id) => fakeTimers.clearTimeout(id),
  });

  const sessionId = lifecycle.open();
  assert.equal(lifecycle.startRoll(sessionId), true);
  assert.equal(lifecycle.finishRoll(sessionId), true);
  assert.equal(lifecycle.scheduleClose(sessionId, 2000), true);
  assert.equal(lifecycle.getState().isRolling, false);

  const [timerId] = fakeTimers.ids();
  assert.equal(fakeTimers.run(timerId), true);
  assert.deepEqual(closed, ["closed"]);
});

test("descarta timers antigos quando o modal é reaberto", () => {
  const fakeTimers = createFakeTimers();
  let closeCount = 0;
  const lifecycle = createRollModalLifecycle({
    onClose: () => {
      closeCount += 1;
    },
    setTimeoutFn: (fn) => fakeTimers.setTimeout(fn),
    clearTimeoutFn: (id) => fakeTimers.clearTimeout(id),
  });

  const firstSession = lifecycle.open();
  lifecycle.scheduleClose(firstSession, 2000);
  const staleTimerId = fakeTimers.ids()[0];

  const secondSession = lifecycle.open();
  lifecycle.scheduleClose(secondSession, 2000);
  const [activeTimerId] = fakeTimers.ids();

  assert.equal(fakeTimers.run(staleTimerId), false);
  assert.equal(closeCount, 0);
  assert.equal(fakeTimers.run(activeTimerId), true);
  assert.equal(closeCount, 1);
});

test("bloqueia múltiplos inícios de rolagem para a mesma sessão e limpa retry", () => {
  const fakeTimers = createFakeTimers();
  const lifecycle = createRollModalLifecycle({
    onClose: () => {},
    setTimeoutFn: (fn) => fakeTimers.setTimeout(fn),
    clearTimeoutFn: (id) => fakeTimers.clearTimeout(id),
  });

  const sessionId = lifecycle.open();
  assert.equal(lifecycle.startRoll(sessionId), true);
  assert.equal(lifecycle.startRoll(sessionId), false);
  assert.equal(lifecycle.scheduleClose(sessionId, 2000), true);
  assert.equal(lifecycle.getState().hasCloseTimer, true);
  assert.equal(lifecycle.resetForRetry(sessionId), true);
  assert.equal(lifecycle.getState().hasCloseTimer, false);
});

test("agenda o fechamento do modal em 2s antes de aguardar a consequência do backend", () => {
  const scriptText = fs.readFileSync(scriptPath, "utf8");
  const scheduleCloseIndex = scriptText.indexOf("rollLifecycle.scheduleClose(rollSessionId, 2000);");
  const awaitResolutionIndex = scriptText.indexOf("const payload = await resolutionPromise;");

  assert.notEqual(scheduleCloseIndex, -1);
  assert.notEqual(awaitResolutionIndex, -1);
  assert.ok(scheduleCloseIndex < awaitResolutionIndex);
});
