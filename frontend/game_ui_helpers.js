(function (globalScope) {
  function resolveTimerFunctions(setTimeoutFn, clearTimeoutFn) {
    const fallbackSetTimeout =
      typeof globalScope.setTimeout === "function" ? globalScope.setTimeout.bind(globalScope) : setTimeout;
    const fallbackClearTimeout =
      typeof globalScope.clearTimeout === "function" ? globalScope.clearTimeout.bind(globalScope) : clearTimeout;

    return {
      setTimeoutFn: typeof setTimeoutFn === "function" ? setTimeoutFn : fallbackSetTimeout,
      clearTimeoutFn: typeof clearTimeoutFn === "function" ? clearTimeoutFn : fallbackClearTimeout,
    };
  }

  function createRollModalLifecycle(options = {}) {
    const { onClose = () => {} } = options;
    const timers = resolveTimerFunctions(options.setTimeoutFn, options.clearTimeoutFn);

    let sessionId = 0;
    let rollingSessionId = null;
    let closeTimerId = null;

    const clearCloseTimer = () => {
      if (closeTimerId !== null) {
        timers.clearTimeoutFn(closeTimerId);
        closeTimerId = null;
      }
    };

    return {
      open() {
        sessionId += 1;
        rollingSessionId = null;
        clearCloseTimer();
        return sessionId;
      },

      startRoll(expectedSessionId) {
        if (expectedSessionId !== sessionId || rollingSessionId === sessionId) {
          return false;
        }

        clearCloseTimer();
        rollingSessionId = sessionId;
        return true;
      },

      finishRoll(expectedSessionId) {
        if (expectedSessionId !== sessionId) {
          return false;
        }

        if (rollingSessionId === sessionId) {
          rollingSessionId = null;
        }
        return true;
      },

      scheduleClose(expectedSessionId, delay = 2000) {
        if (expectedSessionId !== sessionId) {
          return false;
        }

        clearCloseTimer();
        closeTimerId = timers.setTimeoutFn(() => {
          if (expectedSessionId !== sessionId) {
            return;
          }

          closeTimerId = null;
          rollingSessionId = null;
          onClose();
        }, delay);
        return true;
      },

      resetForRetry(expectedSessionId) {
        if (expectedSessionId !== sessionId) {
          return false;
        }

        clearCloseTimer();
        rollingSessionId = null;
        return true;
      },

      cancelClose() {
        clearCloseTimer();
      },

      getSessionId() {
        return sessionId;
      },

      getState() {
        return {
          sessionId,
          isRolling: rollingSessionId === sessionId,
          hasCloseTimer: closeTimerId !== null,
        };
      },
    };
  }

  const api = {
    createRollModalLifecycle,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }

  globalScope.GameUiHelpers = Object.assign(globalScope.GameUiHelpers || {}, api);
})(typeof globalThis !== "undefined" ? globalThis : this);
