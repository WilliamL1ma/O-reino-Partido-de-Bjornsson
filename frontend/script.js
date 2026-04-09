const reveals = document.querySelectorAll(".reveal");

const observer = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      }
    });
  },
  {
    threshold: 0.18,
  }
);

reveals.forEach((element) => observer.observe(element));

const wait = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));

const raceModal = document.getElementById("race-modal");

if (raceModal) {
  const raceButtons = document.querySelectorAll(".js-race-trigger");
  const closeButtons = document.querySelectorAll("[data-close-race-modal]");
  const title = document.getElementById("race-modal-title");
  const description = document.getElementById("race-modal-description");
  const threshold = document.getElementById("race-modal-threshold");
  const status = document.getElementById("race-modal-status");
  const dice = document.getElementById("race-modal-dice");
  const result = document.getElementById("race-modal-result");
  const rollButton = document.getElementById("race-modal-roll");

  let selectedRace = null;
  let rollIntervalId = null;
  let isRolling = false;

  const stopRollAnimation = () => {
    if (rollIntervalId) {
      window.clearInterval(rollIntervalId);
      rollIntervalId = null;
    }
  };

  const resetModalState = () => {
    raceModal.classList.remove(
      "is-open",
      "is-rolling",
      "is-result",
      "is-success",
      "is-failure"
    );
    stopRollAnimation();
    isRolling = false;
  };

  const closeModal = () => {
    if (isRolling) {
      return;
    }

    raceModal.hidden = true;
    selectedRace = null;
    resetModalState();
    dice.textContent = "?";
    result.textContent = "";
    threshold.textContent = "d20";
    status.textContent = "Destino indefinido";
    rollButton.disabled = false;
    rollButton.textContent = "Rolar d20";
  };

  const startRollAnimation = () => {
    let ticks = 0;

    stopRollAnimation();
    raceModal.classList.add("is-rolling");
    raceModal.classList.remove("is-result", "is-success", "is-failure");
    status.textContent = "Tecendo o destino...";

    rollIntervalId = window.setInterval(() => {
      ticks += 1;
      dice.textContent = String(Math.floor(Math.random() * 20) + 1);

      if (ticks % 6 === 0) {
        status.textContent =
          ticks % 12 === 0 ? "Os reinos observam..." : "A sorte ainda gira...";
      }
    }, 90);
  };

  const finishRollAnimation = async (payload) => {
    stopRollAnimation();

    const revealFrames = [18, 11, 15, payload.roll];
    for (const frame of revealFrames) {
      dice.textContent = String(frame);
      await wait(frame === payload.roll ? 220 : 120);
    }

    raceModal.classList.remove("is-rolling");
    raceModal.classList.add("is-result", payload.success ? "is-success" : "is-failure");
    status.textContent = payload.success ? "Destino aceito" : "Destino incompleto";
    result.textContent = payload.message;
  };

  raceButtons.forEach((button) => {
    button.addEventListener("click", () => {
      selectedRace = {
        slug: button.dataset.raceSlug,
        name: button.dataset.raceName,
        threshold: Number(button.dataset.raceThreshold),
        inferior: button.dataset.raceInferior,
      };

      resetModalState();
      title.textContent = selectedRace.name;
      threshold.textContent = `Necessário ${selectedRace.threshold}+ no d20`;
      status.textContent = "Destino indefinido";
      description.textContent =
        `Para se tornar ${selectedRace.name}, você precisa tirar ${selectedRace.threshold} ou mais em um d20. ` +
        `Se falhar, seu personagem se tornará ${selectedRace.inferior} e não receberá o status completo dessa raça até provar seu valor.`;
      dice.textContent = "?";
      result.textContent = "";
      rollButton.disabled = false;
      rollButton.textContent = "Rolar d20";
      raceModal.hidden = false;
      raceModal.classList.add("is-open");
    });
  });

  closeButtons.forEach((button) => {
    button.addEventListener("click", closeModal);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !raceModal.hidden) {
      closeModal();
    }
  });

  rollButton.addEventListener("click", async () => {
    if (!selectedRace || isRolling) {
      return;
    }

    isRolling = true;
    rollButton.disabled = true;
    rollButton.textContent = "Rolando...";
    result.textContent = "";
    startRollAnimation();

    try {
      const startedAt = Date.now();
      const response = await fetch("/jogador/raca/rolar", {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: new URLSearchParams({ race: selectedRace.slug }),
      });

      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        throw new Error(payload.message || "Não foi possível concluir a rolagem.");
      }

      const elapsed = Date.now() - startedAt;
      const minimumAnimationTime = 2200;
      if (elapsed < minimumAnimationTime) {
        await wait(minimumAnimationTime - elapsed);
      }

      await finishRollAnimation(payload);
      isRolling = false;

      window.setTimeout(() => {
        window.location.href = payload.next_url;
      }, 1800);
    } catch (error) {
      resetModalState();
      dice.textContent = "!";
      status.textContent = "Falha na rolagem";
      result.textContent = error.message;
      rollButton.disabled = false;
      rollButton.textContent = "Tentar novamente";
    }
  });
}

const statusModal = document.getElementById("status-modal");

if (statusModal) {
  const openButton = document.querySelector(".js-status-modal-open");
  const progress = document.getElementById("status-modal-progress");
  const current = document.getElementById("status-modal-current");
  const dice = document.getElementById("status-modal-dice");
  const result = document.getElementById("status-modal-result");
  const rollButton = document.getElementById("status-modal-roll");
  const chips = document.querySelectorAll("[data-status-chip]");
  const order = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma", "perception"];
  const labels = {
    strength: "FOR",
    dexterity: "DEX",
    constitution: "CON",
    intelligence: "INT",
    wisdom: "SAB",
    charisma: "CAR",
    perception: "PER",
  };

  let rolling = false;
  let rolledCount = document.querySelectorAll(".status-roll-chip.is-done").length;

  const updateProgress = () => {
    progress.textContent = `${rolledCount}/${order.length} rolados`;
    const nextField = order[rolledCount];
    current.textContent = nextField ? `Próximo: ${labels[nextField]}` : "Status completos";
  };

  const resetDiceState = () => {
    statusModal.classList.remove("is-result", "is-success", "is-failure");
    statusModal.classList.add("is-rolling");
    result.textContent = "";
  };

  const animateStatusRoll = async (finalValue) => {
    for (let index = 0; index < 16; index += 1) {
      dice.textContent = String(Math.floor(Math.random() * 20) + 1);
      await wait(75);
    }

    const revealFrames = [17, 8, 14, finalValue];
    for (const frame of revealFrames) {
      dice.textContent = String(frame);
      await wait(frame === finalValue ? 220 : 120);
    }
  };

  openButton?.addEventListener("click", () => {
    statusModal.hidden = false;
    statusModal.classList.add("is-open");
    statusModal.classList.remove("is-success", "is-failure");
    updateProgress();
  });

  rollButton?.addEventListener("click", async () => {
    if (rolling) {
      return;
    }

    rolling = true;
    rollButton.disabled = true;
    rollButton.textContent = "Rolando...";
    resetDiceState();

    try {
      const response = await fetch("/jogador/status/rolar-modal", {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
      });

      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        throw new Error(payload.message || "Não foi possível rolar os status.");
      }

      if (payload.completed && !payload.attribute) {
        window.location.href = payload.next_url;
        return;
      }

      await animateStatusRoll(payload.roll);

      const chip = document.querySelector(`[data-status-chip="${payload.attribute}"] strong`);
      const chipCard = document.querySelector(`[data-status-chip="${payload.attribute}"]`);
      if (chip) {
        chip.textContent = String(payload.roll);
      }
      chipCard?.classList.add("is-done");

      rolledCount += 1;
      updateProgress();
      statusModal.classList.remove("is-rolling");
      statusModal.classList.add("is-result", "is-success");
      result.textContent = payload.message;

      if (payload.completed) {
        current.textContent = "Todos os status foram revelados";
        rollButton.textContent = "Finalizando...";
        await wait(1400);
        window.location.href = payload.next_url;
        return;
      }

      rollButton.disabled = false;
      rollButton.textContent = "Rolar";
    } catch (error) {
      statusModal.classList.remove("is-rolling");
      statusModal.classList.add("is-result", "is-failure");
      dice.textContent = "!";
      result.textContent = error.message;
      rollButton.disabled = false;
      rollButton.textContent = "Rolar";
    } finally {
      rolling = false;
    }
  });
}

const classInfoButtons = document.querySelectorAll(".js-class-info");

if (classInfoButtons.length > 0) {
  classInfoButtons.forEach((button) => {
    button.addEventListener("click", (event) => {
      event.preventDefault();

      const card = button.closest(".js-class-card");
      if (!card) {
        return;
      }

      const shouldFlip = !card.classList.contains("is-flipped");
      card.classList.toggle("is-flipped", shouldFlip);

      card.querySelectorAll(".js-class-info").forEach((infoButton) => {
        infoButton.setAttribute("aria-expanded", String(shouldFlip));
      });
    });
  });
}

const gameChatForm = document.getElementById("game-chat-form");
const gameRollModal = document.getElementById("game-roll-modal");
const gameUiHelpers = window.GameUiHelpers || {};
const createRollModalLifecycle =
  typeof gameUiHelpers.createRollModalLifecycle === "function"
    ? gameUiHelpers.createRollModalLifecycle
    : ({ onClose = () => {} } = {}) => ({
        open() {
          return Date.now();
        },
        startRoll() {
          return true;
        },
        finishRoll() {
          return true;
        },
        scheduleClose(_sessionId, delay = 2000) {
          window.setTimeout(() => onClose(), delay);
          return true;
        },
        resetForRetry() {
          return true;
        },
        cancelClose() {},
        getSessionId() {
          return 0;
        },
      });

let openGameRollModal = null;
let closeGameRollModal = null;
let scheduleGameRollModalOpen = null;
let syncGameViewState = null;

const buildPendingEventDescription = (pendingEvent) => {
  if (!pendingEvent || typeof pendingEvent !== "object") {
    return "Resolva o evento pendente para continuar.";
  }

  if (pendingEvent.type === "encounter" && pendingEvent.monster_name) {
    return `${pendingEvent.monster_name} surgiu no caminho. ${
      pendingEvent.stakes || "O choque precisa ser resolvido antes de seguir."
    }`;
  }

  return pendingEvent.stakes || "Resolva o evento pendente para continuar.";
};

if (gameRollModal) {
  const openRollButton = document.querySelector(".js-open-roll-modal");
  const rollButton = document.getElementById("game-roll-button");
  const title = document.getElementById("game-roll-title");
  const stakes = document.getElementById("game-roll-stakes");
  const attribute = document.getElementById("game-roll-attribute");
  const difficulty = document.getElementById("game-roll-difficulty");
  const dice = document.getElementById("game-roll-dice");
  const result = document.getElementById("game-roll-result");
  const rollLifecycle = createRollModalLifecycle({
    onClose: () => {
      gameRollModal.hidden = true;
      gameRollModal.classList.remove("is-open");
    },
    setTimeoutFn: window.setTimeout.bind(window),
    clearTimeoutFn: window.clearTimeout.bind(window),
  });

  let rolling = false;
  let activeRollSessionId = 0;
  let autoOpenTimerId = null;
  let pendingEventData = null;

  const clearAutoOpenTimer = () => {
    if (autoOpenTimerId !== null) {
      window.clearTimeout(autoOpenTimerId);
      autoOpenTimerId = null;
    }
  };

  const buildEventDataFromButton = (button) => {
    if (!button) {
      return null;
    }

    return {
      type: button.dataset.eventType,
      roll_type: button.dataset.rollType,
      attribute: button.dataset.attribute,
      label: button.dataset.label,
      difficulty: button.dataset.difficulty,
      stakes: button.dataset.stakes,
      monster_name: button.dataset.monsterName,
    };
  };

  const resetRollModal = () => {
    dice.textContent = "?";
    result.textContent = "";
    rollButton.disabled = false;
    rollButton.textContent = "Rolar d20";
  };

  openGameRollModal = (eventData) => {
    if (!eventData || rolling) {
      return;
    }

    clearAutoOpenTimer();
    rollLifecycle.cancelClose();
    pendingEventData = eventData;
    activeRollSessionId = rollLifecycle.open();

    title.textContent =
      eventData.type === "encounter"
        ? `${eventData.monster_name || "Uma criatura"} exige reflexo imediato.`
        : "O mestre pediu um teste.";
    stakes.textContent = eventData.stakes || "Resolva o evento pendente para prosseguir.";
    attribute.textContent = eventData.label || "ATRIBUTO";
    difficulty.textContent = `CD ${eventData.difficulty || "12"}`;
    resetRollModal();

    gameRollModal.hidden = false;
    gameRollModal.classList.add("is-open");
  };

  closeGameRollModal = () => {
    clearAutoOpenTimer();
    rollLifecycle.cancelClose();
    rolling = false;
    pendingEventData = null;
    gameRollModal.hidden = true;
    gameRollModal.classList.remove("is-open");
  };

  scheduleGameRollModalOpen = (eventData, delay = 250) => {
    if (!eventData) {
      return;
    }

    clearAutoOpenTimer();
    autoOpenTimerId = window.setTimeout(() => {
      autoOpenTimerId = null;
      if (typeof openGameRollModal === "function") {
        openGameRollModal(eventData);
      }
    }, delay);
  };

  openRollButton?.addEventListener("click", () => {
    if (typeof openGameRollModal === "function") {
      openGameRollModal(buildEventDataFromButton(openRollButton));
    }
  });

  if (openRollButton) {
    scheduleGameRollModalOpen(buildEventDataFromButton(openRollButton));
  }

  const animateRoll = async (finalValue) => {
    for (let index = 0; index < 12; index += 1) {
      dice.textContent = String(Math.floor(Math.random() * 20) + 1);
      await wait(70);
    }

    const revealFrames = [16, 11, finalValue];
    for (const frame of revealFrames) {
      dice.textContent = String(frame);
      await wait(frame === finalValue ? 260 : 160);
    }
  };

  rollButton?.addEventListener("click", async () => {
    const rollSessionId = activeRollSessionId || rollLifecycle.getSessionId();
    if (!pendingEventData || !rollLifecycle.startRoll(rollSessionId)) {
      return;
    }

    rolling = true;
    rollButton.disabled = true;
    rollButton.textContent = "Rolando...";
    result.textContent = "";

    const chatMessages = document.getElementById("game-chat-messages");
    let thinkingArticle = null;
    let thinkingParagraph = null;
    let thinkingIntervalId = null;

    try {
      const startResponse = await fetch("/jogo/rolar", {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
      });
      const startPayload = await startResponse.json();
      if (!startResponse.ok || !startPayload.ok) {
        throw new Error(startPayload.message || "Não foi possível iniciar a rolagem.");
      }

      const resolutionPromise = fetch("/jogo/rolar/consequencia", {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
      }).then(async (response) => {
        const payload = await response.json();
        if (!response.ok || !payload.ok) {
          throw new Error(payload.message || "Não foi possível resolver a rolagem.");
        }
        return payload;
      });

      await animateRoll(startPayload.roll);
      rollLifecycle.finishRoll(rollSessionId);
      result.textContent =
        `${startPayload.outcome_label || "resultado"}: ${startPayload.attribute_label} rolou ${startPayload.roll} + ${startPayload.attribute_bonus}, total ${startPayload.total} contra CD ${startPayload.difficulty}.`;
      rollLifecycle.scheduleClose(rollSessionId, 2000);

      if (chatMessages) {
        thinkingArticle = document.createElement("article");
        thinkingArticle.className = "game-chat__message game-chat__message--gm game-chat__message--thinking";
        const strong = document.createElement("strong");
        strong.textContent = "Mestre";
        thinkingParagraph = document.createElement("p");
        thinkingParagraph.textContent = "pensando.";
        thinkingArticle.appendChild(strong);
        thinkingArticle.appendChild(thinkingParagraph);
        chatMessages.appendChild(thinkingArticle);
        chatMessages.scrollTop = chatMessages.scrollHeight;

        const frames = ["pensando.", "pensando..", "pensando..."];
        let frameIndex = 0;
        thinkingIntervalId = window.setInterval(() => {
          frameIndex = (frameIndex + 1) % frames.length;
          if (thinkingParagraph) {
            thinkingParagraph.textContent = frames[frameIndex];
          }
        }, 420);
      }

      const payload = await resolutionPromise;
      pendingEventData = payload.view_state?.pending_event || null;

      window.clearInterval(thinkingIntervalId);
      if (thinkingArticle && thinkingParagraph) {
        thinkingArticle.classList.remove("game-chat__message--thinking");
        thinkingParagraph.textContent = payload.gm_message;
      }

      if (payload.monster_name && Array.isArray(payload.loot_names) && payload.loot_names.length > 0) {
        result.textContent += ` Drops recebidos de ${payload.monster_name}: ${payload.loot_names.join(", ")}.`;
      }

      if (typeof syncGameViewState === "function") {
        syncGameViewState(payload.view_state, {
          suggestedActions: payload.suggested_actions,
          pendingEvent: payload.view_state?.pending_event ?? null,
        });
      }

      rolling = false;
    } catch (error) {
      rollLifecycle.resetForRetry(rollSessionId);
      window.clearInterval(thinkingIntervalId);
      if (thinkingArticle && thinkingParagraph) {
        thinkingArticle.classList.remove("game-chat__message--thinking");
        thinkingParagraph.textContent =
          "O mestre demora mais do que o esperado para fechar essa consequência. Tente novamente.";
      }

      dice.textContent = "!";
      result.textContent = "A rolagem vacilou por um instante. Tente novamente.";
      if (!gameRollModal.hidden) {
        rollButton.disabled = false;
        rollButton.textContent = "Rolar d20";
      }
      rolling = false;
      console.error(error);
    }
  });
}

if (gameChatForm) {
  const chatInput = document.getElementById("game-chat-input");
  const chatSubmit = document.getElementById("game-chat-submit");
  const chatMessages = document.getElementById("game-chat-messages");
  const gamePanel = document.querySelector(".game-panel");
  const mainChatCard = document.querySelector(".game-chat--main");
  const suggestionPanel = document.getElementById("game-suggestions-panel");
  const suggestionList = document.getElementById("game-suggestions-list");
  const currentMomentTitle = document.getElementById("game-current-moment-title");
  const currentMomentDescription = document.getElementById("game-current-moment-description");
  const sceneEyebrow = document.getElementById("game-scene-eyebrow");
  const progressAct = document.getElementById("game-progress-act");
  const progressXp = document.getElementById("game-progress-xp");
  const progressGold = document.getElementById("game-progress-gold");
  const progressSceneTitle = document.getElementById("game-progress-scene-title");
  const inventoryList = document.getElementById("game-inventory-list");
  const recentRewardPanel = document.getElementById("game-recent-reward-panel");
  const recentRewardMonster = document.getElementById("game-recent-reward-monster");
  const recentRewardXp = document.getElementById("game-recent-reward-xp");
  const recentRewardGold = document.getElementById("game-recent-reward-gold");
  const recentRewardLoot = document.getElementById("game-recent-reward-loot");
  const findPendingEventBanner = () => document.querySelector(".game-event-banner");

  const setText = (element, value) => {
    if (!element) {
      return;
    }

    element.textContent = value == null ? "" : String(value);
  };

  const setChatAvailability = (blocked) => {
    if (!chatInput || !chatSubmit) {
      return;
    }

    chatInput.disabled = blocked;
    chatSubmit.disabled = blocked;
    chatSubmit.textContent = blocked ? "Rolagem pendente" : "Falar com o mestre";
  };

  const renderSuggestions = (actions = [], { blocked = false } = {}) => {
    if (suggestionPanel) {
      suggestionPanel.hidden = false;
    }

    if (!suggestionList) {
      return;
    }

    suggestionList.innerHTML = "";
    if (blocked) {
      const item = document.createElement("li");
      item.textContent = "As sugestões ficam disponíveis novamente depois que a rolagem pendente for resolvida.";
      suggestionList.appendChild(item);
      return;
    }

    if (!Array.isArray(actions) || actions.length === 0) {
      const item = document.createElement("li");
      item.textContent = "As próximas opções aparecerão aqui quando o mestre sugerir caminhos.";
      suggestionList.appendChild(item);
      return;
    }

    actions.slice(0, 5).forEach((action) => {
      const item = document.createElement("li");
      item.textContent = action;
      suggestionList.appendChild(item);
    });
  };

  const appendChatMessage = (role, content, { loading = false } = {}) => {
    const article = document.createElement("article");
    article.className = `game-chat__message game-chat__message--${role}`;
    if (loading) {
      article.classList.add("game-chat__message--thinking");
    }

    const title = document.createElement("strong");
    title.textContent = role === "gm" ? "Mestre" : "Você";

    const paragraph = document.createElement("p");
    paragraph.textContent = content;

    article.appendChild(title);
    article.appendChild(paragraph);

    chatMessages.appendChild(article);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return article;
  };

  const startThinkingIndicator = () => {
    const article = appendChatMessage("gm", "pensando.", { loading: true });
    const paragraph = article.querySelector("p");
    const frames = ["pensando.", "pensando..", "pensando..."];
    let frameIndex = 0;
    const intervalId = window.setInterval(() => {
      frameIndex = (frameIndex + 1) % frames.length;
      if (paragraph) {
        paragraph.textContent = frames[frameIndex];
      }
    }, 420);

    return {
      resolve(content) {
        window.clearInterval(intervalId);
        article.classList.remove("game-chat__message--thinking");
        if (paragraph) {
          paragraph.textContent = content;
        }
      },
      remove() {
        window.clearInterval(intervalId);
        article.remove();
      },
    };
  };

  const renderInventoryPreview = (items) => {
    if (!inventoryList || !Array.isArray(items)) {
      return;
    }

    inventoryList.innerHTML = "";
    if (items.length === 0) {
      const item = document.createElement("li");
      item.textContent = "Nenhum item coletado ainda.";
      inventoryList.appendChild(item);
      return;
    }

    items.forEach((entry) => {
      const item = document.createElement("li");
      const strong = document.createElement("strong");
      strong.textContent = entry.name || "Item sem nome";
      item.appendChild(strong);

      if (entry.value != null) {
        const value = document.createElement("span");
        value.textContent = ` (${entry.value} ouro)`;
        item.appendChild(value);
      }

      inventoryList.appendChild(item);
    });
  };

  const renderRecentReward = (recentReward) => {
    if (!recentRewardPanel) {
      return;
    }

    if (!recentReward || typeof recentReward !== "object") {
      recentRewardPanel.hidden = true;
      setText(recentRewardMonster, "");
      setText(recentRewardXp, "");
      setText(recentRewardGold, "");
      setText(recentRewardLoot, "");
      return;
    }

    recentRewardPanel.hidden = false;
    setText(recentRewardMonster, recentReward.monster_name || "");
    setText(recentRewardXp, recentReward.xp_gain ?? "");
    setText(recentRewardGold, recentReward.gold_gain ?? "");
    if (Array.isArray(recentReward.loot_names) && recentReward.loot_names.length > 0) {
      setText(recentRewardLoot, recentReward.loot_names.join(", "));
    } else {
      setText(recentRewardLoot, "Nenhum item raro");
    }
  };

  const updateCurrentMoment = (moment) => {
    if (!moment || typeof moment !== "object") {
      return;
    }

    if (currentMomentTitle && typeof moment.title === "string" && moment.title.trim()) {
      currentMomentTitle.textContent = moment.title.trim();
    }

    if (currentMomentDescription && typeof moment.description === "string" && moment.description.trim()) {
      currentMomentDescription.textContent = moment.description.trim();
    }
  };

  const syncPendingEvent = (pendingEvent) => {
    const currentBanner = findPendingEventBanner();

    if (!pendingEvent) {
      currentBanner?.remove();
      setChatAvailability(false);
      return;
    }

    let banner = currentBanner;
    if (!banner) {
      banner = document.createElement("div");
      banner.className = "game-event-banner";
      if (gamePanel && mainChatCard) {
        gamePanel.insertBefore(banner, mainChatCard);
      }
    }

    banner.innerHTML = "";
    const label = document.createElement("strong");
    label.textContent = "Rolagem pendente:";

    const description = document.createElement("span");
    description.textContent = buildPendingEventDescription(pendingEvent);

    const button = document.createElement("button");
    button.className = "button button--primary";
    button.type = "button";
    button.textContent = "Rolar d20 agora";
    button.addEventListener("click", () => {
      if (typeof openGameRollModal === "function") {
        openGameRollModal(pendingEvent);
      }
    });

    banner.appendChild(label);
    banner.appendChild(description);
    banner.appendChild(button);

    setChatAvailability(true);
    renderSuggestions([], { blocked: true });
  };

  const applyViewState = (viewState, overrides = {}) => {
    const state = viewState && typeof viewState === "object" ? viewState : {};
    const sceneState = state.scene && typeof state.scene === "object" ? state.scene : {};
    const progressState = state.progress && typeof state.progress === "object" ? state.progress : {};

    if (sceneEyebrow && typeof sceneState.eyebrow === "string" && sceneState.eyebrow.trim()) {
      sceneEyebrow.textContent = sceneState.eyebrow.trim();
    }
    if (progressAct && progressState.act != null) {
      progressAct.textContent = String(progressState.act);
    }
    if (progressXp && progressState.experience != null) {
      progressXp.textContent = String(progressState.experience);
    }
    if (progressGold && progressState.gold != null) {
      progressGold.textContent = String(progressState.gold);
    }
    if (progressSceneTitle && typeof sceneState.title === "string" && sceneState.title.trim()) {
      progressSceneTitle.textContent = sceneState.title.trim();
    }

    if (Array.isArray(state.inventory_preview)) {
      renderInventoryPreview(state.inventory_preview);
    }
    if ("recent_reward" in state) {
      renderRecentReward(state.recent_reward);
    }

    const currentMoment =
      Object.prototype.hasOwnProperty.call(overrides, "currentMoment") ? overrides.currentMoment : state.current_moment;
    updateCurrentMoment(currentMoment);

    const pendingEvent =
      Object.prototype.hasOwnProperty.call(overrides, "pendingEvent") ? overrides.pendingEvent : state.pending_event;
    const suggestedActions =
      Object.prototype.hasOwnProperty.call(overrides, "suggestedActions")
        ? overrides.suggestedActions
        : state.suggested_actions;

    renderSuggestions(suggestedActions, { blocked: Boolean(pendingEvent) });
    syncPendingEvent(pendingEvent);
  };

  syncGameViewState = applyViewState;

  gameChatForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const message = chatInput?.value.trim();
    if (!message || !chatInput || !chatSubmit || !chatMessages) {
      return;
    }

    chatInput.disabled = true;
    chatSubmit.disabled = true;
    chatSubmit.textContent = "Consultando...";
    appendChatMessage("player", message);
    chatInput.value = "";
    const thinking = startThinkingIndicator();

    try {
      const response = await fetch("/jogo/mestre", {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: new URLSearchParams({ message }),
      });

      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        throw new Error(payload.message || "Não foi possível falar com o mestre.");
      }

      const gmMessage = String(payload.gm_message || "").trim();
      if (gmMessage) {
        thinking.resolve(gmMessage);
      } else {
        thinking.remove();
      }

      applyViewState(payload.view_state, {
        suggestedActions: payload.suggested_actions,
        currentMoment: payload.current_moment,
        pendingEvent: payload.pending_event,
      });

      if (payload.pending_event && typeof scheduleGameRollModalOpen === "function") {
        scheduleGameRollModalOpen(payload.pending_event, 260);
      }
    } catch (error) {
      thinking.resolve("O mestre hesita por um instante, como se a cena ainda estivesse se formando. Tente novamente.");
      console.error(error);
    } finally {
      if (!findPendingEventBanner()) {
        chatInput.disabled = false;
        chatSubmit.disabled = false;
        chatSubmit.textContent = "Falar com o mestre";
        chatInput.focus();
      }
    }
  });
}
