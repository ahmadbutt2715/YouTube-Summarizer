function getCsrfToken() {
  const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
  return input ? input.value : "";
}

async function postJSON(url, data) {
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCsrfToken(),
    },
    body: JSON.stringify(data),
  });
  const body = await res.json();
  if (!res.ok) {
    throw new Error(body.error || "Something went wrong.");
  }
  return body;
}

function el(id) {
  return document.getElementById(id);
}

function addBubble(role, text) {
  const log = el("chat-log");
  const placeholder = el("chat-placeholder");
  if (placeholder) placeholder.remove();

  const bubble = document.createElement("div");
  bubble.className = `bubble bubble--${role}`;
  bubble.textContent = text;
  log.appendChild(bubble);
  log.scrollTop = log.scrollHeight;
  return bubble;
}

function setChatEnabled(enabled) {
  el("chat-input").disabled = !enabled;
  el("ask-btn").disabled = !enabled;
}

// --- Video load ---
el("video-form").addEventListener("submit", async (e) => {
  e.preventDefault();

  const urlInput = el("video-url");
  const errorEl = el("video-error");
  const loadBtn = el("load-btn");

  errorEl.hidden = true;
  loadBtn.disabled = true;
  loadBtn.textContent = "Loading…";

  try {
    const data = await postJSON("/api/load-video/", { video_url: urlInput.value.trim() });

    el("video-empty").hidden = true;
    const card = el("video-card");
    card.hidden = false;
    el("video-id-badge").textContent = data.video_id;
    el("video-title").textContent = data.title;
    el("video-summary").textContent = data.summary;

    // Reset chat for the new video.
    const log = el("chat-log");
    log.innerHTML = '<div class="chat-placeholder" id="chat-placeholder">Ask your first question about this video below.</div>';
    setChatEnabled(true);
    el("chat-input").focus();
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.hidden = false;
  } finally {
    loadBtn.disabled = false;
    loadBtn.textContent = "Load";
  }
});

// --- Chat ---
el("chat-form").addEventListener("submit", async (e) => {
  e.preventDefault();

  const input = el("chat-input");
  const question = input.value.trim();
  if (!question) return;

  addBubble("user", question);
  input.value = "";
  setChatEnabled(false);

  const pending = addBubble("assistant", "Thinking…");
  pending.classList.add("bubble--pending");

  try {
    const data = await postJSON("/api/ask/", { question });
    pending.textContent = data.answer;
    pending.classList.remove("bubble--pending");
  } catch (err) {
    pending.textContent = err.message;
    pending.classList.remove("bubble--pending");
  } finally {
    setChatEnabled(true);
    input.focus();
  }
});
