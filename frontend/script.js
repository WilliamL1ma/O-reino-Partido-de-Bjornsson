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
      threshold.textContent = `Necessario ${selectedRace.threshold}+ no d20`;
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
    current.textContent = nextField ? `Proximo: ${labels[nextField]}` : "Status completos";
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
let openGameRollModal = null;
let closeGameRollModal = null;

if (gameRollModal) {
  let openRollButton = document.querySelector(".js-open-roll-modal");
  const rollButton = document.getElementById("game-roll-button");
  const title = document.getElementById("game-roll-title");
  const stakes = document.getElementById("game-roll-stakes");
  const attribute = document.getElementById("game-roll-attribute");
  const difficulty = document.getElementById("game-roll-difficulty");
  const dice = document.getElementById("game-roll-dice");
  const result = document.getElementById("game-roll-result");

  let rolling = false;

  openGameRollModal = (eventData) => {
    if (!eventData) {
      return;
    }

    title.textContent =
      eventData.type === "encounter"
        ? `${eventData.monster_name || "Uma criatura"} exige reflexo imediato.`
        : "O mestre pediu um teste.";
    stakes.textContent = eventData.stakes || "Resolva o evento pendente para prosseguir.";
    attribute.textContent = eventData.label || "ATRIBUTO";
    difficulty.textContent = `CD ${eventData.difficulty || "12"}`;
    dice.textContent = "?";
    result.textContent = "";
    rollButton.disabled = false;
    rollButton.textContent = "Rolar d20";
    gameRollModal.hidden = false;
    gameRollModal.classList.add("is-open");
  };

  closeGameRollModal = () => {
    gameRollModal.hidden = true;
    gameRollModal.classList.remove("is-open");
  };

  openRollButton?.addEventListener("click", () => {
    openGameRollModal({
      type: openRollButton.dataset.eventType,
      roll_type: openRollButton.dataset.rollType,
      attribute: openRollButton.dataset.attribute,
      label: openRollButton.dataset.label,
      difficulty: openRollButton.dataset.difficulty,
      stakes: openRollButton.dataset.stakes,
      monster_name: openRollButton.dataset.monsterName,
    });
  });

  if (openRollButton) {
    window.setTimeout(() => {
      openGameRollModal({
        type: openRollButton.dataset.eventType,
        roll_type: openRollButton.dataset.rollType,
        attribute: openRollButton.dataset.attribute,
        label: openRollButton.dataset.label,
        difficulty: openRollButton.dataset.difficulty,
        stakes: openRollButton.dataset.stakes,
        monster_name: openRollButton.dataset.monsterName,
      });
    }, 250);
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
    if (rolling) {
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
      result.textContent =
        `${startPayload.outcome_label || "resultado"}: ${startPayload.attribute_label} rolou ${startPayload.roll} + ${startPayload.attribute_bonus}, total ${startPayload.total} contra CD ${startPayload.difficulty}.`;
      window.setTimeout(() => {
        if (rolling) {
          closeGameRollModal?.();
        }
      }, 2000);

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

      window.clearInterval(thinkingIntervalId);
      if (thinkingArticle && thinkingParagraph) {
        thinkingArticle.classList.remove("game-chat__message--thinking");
        thinkingParagraph.textContent = payload.gm_message;
      }

      if (payload.monster_name && Array.isArray(payload.loot_names) && payload.loot_names.length > 0) {
        result.textContent += ` Drops recebidos de ${payload.monster_name}: ${payload.loot_names.join(", ")}.`;
      }

      const suggestionPanel = document.getElementById("game-suggestions-panel");
      const suggestionList = document.getElementById("game-suggestions-list");
      if (suggestionPanel) {
        suggestionPanel.hidden = false;
      }
      if (suggestionList) {
        suggestionList.innerHTML = "";
        if (Array.isArray(payload.suggested_actions) && payload.suggested_actions.length > 0) {
          payload.suggested_actions.slice(0, 5).forEach((action) => {
            const item = document.createElement("li");
            item.textContent = action;
            suggestionList.appendChild(item);
          });
        } else {
          const item = document.createElement("li");
          item.textContent = "As próximas opções aparecerão aqui quando o mestre sugerir caminhos.";
          suggestionList.appendChild(item);
        }
      }

      document.querySelector(".game-event-banner")?.remove();

      const chatInput = document.getElementById("game-chat-input");
      const chatSubmit = document.getElementById("game-chat-submit");
      if (chatInput && chatSubmit) {
        chatInput.disabled = false;
        chatSubmit.disabled = false;
        chatSubmit.textContent = "Falar com o mestre";
      }
      rolling = false;
    } catch (error) {
      window.clearInterval(thinkingIntervalId);
      if (thinkingArticle && thinkingParagraph) {
        thinkingArticle.classList.remove("game-chat__message--thinking");
        thinkingParagraph.textContent = "O mestre demora mais do que o esperado para fechar essa consequência. Tente novamente.";
      }
      dice.textContent = "!";
      result.textContent = "A rolagem vacilou por um instante. Tente novamente.";
      rollButton.disabled = false;
      rollButton.textContent = "Rolar d20";
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
  const findPendingEventBanner = () => document.querySelector(".game-event-banner");

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
    title.textContent = role === "gm" ? "Mestre" : "Voce";

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
    description.textContent =
      pendingEvent.type === "encounter" && pendingEvent.monster_name
        ? `${pendingEvent.monster_name} surgiu no caminho. ${pendingEvent.stakes}`
        : pendingEvent.stakes || "Resolva o evento pendente para continuar.";

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

      if (payload.pending_event && !String(payload.gm_message || "").trim()) {
        thinking.remove();
      } else {
        thinking.resolve(payload.gm_message);
      }
      renderSuggestions(payload.suggested_actions, { blocked: Boolean(payload.pending_event) });
      updateCurrentMoment(payload.current_moment);
      syncPendingEvent(payload.pending_event);

      if (payload.next_scene) {
        window.setTimeout(() => window.location.reload(), 900);
        return;
      }

      if (payload.pending_event && typeof openGameRollModal === "function") {
        window.setTimeout(() => openGameRollModal(payload.pending_event), 260);
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
