const container = document.getElementById("profile-container");
const userId = container?.dataset?.userId;

async function fetchJson(url) {
  const res = await fetch(url, { credentials: "include" });
  return res.json();
}

async function fetchJsonWithOptions(url, options) {
  const res = await fetch(url, { credentials: "include", ...options });
  return res.json();
}

async function resolveUserId() {
  if (userId && userId !== "me") {
    return userId;
  }
  const me = await fetchJson("/api/me");
  return me.logged_in ? me.user_id : null;
}

function renderProfile(profile) {
  const card = document.getElementById("profile-card");
  const isSelf = profile.is_self;
  card.innerHTML = `
    <div class="row" style="align-items:center; gap:24px;">
      <img src="${profile.avatar_url}" alt="${profile.username}" style="width:120px;height:120px;border-radius:20px;object-fit:cover;border:1px solid rgba(148,163,184,0.4);" />
      <div style="flex:1;">
        <div class="title">${profile.username}</div>
        <div class="subtitle">身份：${profile.role === "publisher" ? "发行商" : "玩家"}</div>
        <div class="balance-row">
          <span class="balance-label">💰 账户余额</span>
          <span class="balance-amount" id="balance-amount">￥${profile.balance.toFixed(2)}</span>
        </div>
        ${isSelf ? `
          <div class="top-up-row">
            <input type="number" id="top-up-amount" min="1" step="1" placeholder="输入充值金额" />
            <button class="btn" id="top-up-btn">充值</button>
          </div>
        ` : ""}
      </div>
    </div>
  `;

  if (isSelf) {
    document.getElementById("top-up-btn").addEventListener("click", handleTopUp);
    document.getElementById("top-up-amount").addEventListener("keydown", (e) => {
      if (e.key === "Enter") handleTopUp();
    });
  }
}


async function handleTopUp() {
  const input = document.getElementById("top-up-amount");
  const amount = parseInt(input.value, 10);

  if (!amount || amount <= 0 || !Number.isInteger(amount)) {
    alert("请输入大于 0 的整数金额");
    return;
  }

  // Show custom confirmation modal
  const overlay = document.getElementById("success-overlay");
  overlay.innerHTML = `
    <div class="confirm-modal">
      <div class="confirm-title">确认充值</div>
      <div class="confirm-amount">￥${amount}</div>
      <div class="confirm-actions">
        <button class="btn" id="confirm-yes">确认充值</button>
        <button class="btn secondary" id="confirm-no">取消</button>
      </div>
    </div>
  `;
  overlay.style.display = "flex";

  // Wait for user confirmation
  const result = await new Promise((resolve) => {
    document.getElementById("confirm-yes").addEventListener("click", () => {
      // Disable button immediately to prevent double-click
      document.getElementById("confirm-yes").disabled = true;
      document.getElementById("confirm-yes").textContent = "处理中...";
      resolve(true);
    });
    document.getElementById("confirm-no").addEventListener("click", () => resolve(false));
  });

  if (!result) {
    overlay.style.display = "none";
    overlay.innerHTML = "";
    return;
  }

  // User confirmed — call API
  const res = await fetch("/api/top-up", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ amount }),
  });
  const apiResult = await res.json();

  if (apiResult.error) {
    overlay.style.display = "none";
    overlay.innerHTML = "";
    alert(apiResult.error);
    return;
  }

  // Update balance display
  document.getElementById("balance-amount").textContent = `￥${apiResult.balance.toFixed(2)}`;
  input.value = "";

  // Show success animation
  overlay.innerHTML = `
    <div class="success-animation">
      <svg class="success-svg" viewBox="0 0 52 52">
        <circle class="circle-path" cx="26" cy="26" r="24" fill="none" stroke="#4ade80" stroke-width="3"/>
        <polyline class="check-path" points="14,27 23,36 38,18" fill="none" stroke="#4ade80" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
        <text x="26" y="52" text-anchor="middle" fill="white" font-size="10" font-weight="600">充值成功</text>

      </svg>
    </div>
  `;





  // Hide after 2s
  setTimeout(() => {
    overlay.style.display = "none";
    overlay.innerHTML = "";
  }, 2000);
}



function renderFriendAction(profile) {
  const container = document.getElementById("friend-action");
  if (!container) return;
  if (profile.is_self) {
    container.style.display = "none";
    return;
  }
  container.style.display = "block";

  if (profile.is_friend) {
    container.innerHTML = `<div class="title">你们已成为好友</div><div class="subtitle">可以在好友列表中查看对方主页</div>`;
    return;
  }

  if (profile.pending_request === "sent") {
    container.innerHTML = `<div class="title">好友申请已发送</div><div class="subtitle">等待对方通过</div>`;
    return;
  }

  if (profile.pending_request === "received") {
    container.innerHTML = `
      <div class="title">收到好友申请</div>
      <div class="subtitle">对方希望添加你为好友</div>
      <div class="friend-actions">
        <button class="btn" id="accept-request">通过</button>
        <button class="btn secondary" id="reject-request">拒绝</button>
      </div>
    `;
    document.getElementById("accept-request").addEventListener("click", async () => {
      await fetchJsonWithOptions(`/api/friends/requests/${profile.pending_request_id}/accept`, {
        method: "POST",
      });
      window.location.reload();
    });
    document.getElementById("reject-request").addEventListener("click", async () => {
      await fetchJsonWithOptions(`/api/friends/requests/${profile.pending_request_id}/reject`, {
        method: "POST",
      });
      window.location.reload();
    });
    return;
  }

  container.innerHTML = `
    <div class="title">添加好友</div>
    <div class="subtitle">可以附上一段 30 字以内说明</div>
    <div class="reply-form">
      <input type="text" id="friend-message" maxlength="30" placeholder="打个招呼吧" />
      <button class="btn" id="friend-add-btn">发送申请</button>
    </div>
    <p class="notice" id="friend-action-msg"></p>
  `;
  document.getElementById("friend-add-btn").addEventListener("click", async () => {
    const message = document.getElementById("friend-message").value.trim();
    const result = await fetchJsonWithOptions("/api/friends/requests", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ to_user_id: profile.user_id, message }),
    });
    const msg = document.getElementById("friend-action-msg");
    if (result.error) {
      msg.textContent = `发送失败：${result.error}`;
      msg.classList.add("status-error");
      return;
    }
    msg.textContent = "好友申请已发送";
    msg.classList.remove("status-error");
  });
}


function renderOwnedGames(games) {
  const grid = document.getElementById("owned-games");
  const empty = document.getElementById("owned-empty");
  grid.innerHTML = "";
  if (!games || games.length === 0) {
    empty.textContent = "还没有购买任何游戏。";
    return;
  }
  empty.textContent = "";
  games.forEach((game) => {
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
      <img src="${game.cover_url}" alt="${game.title}" />
      <h3>${game.title}</h3>
      <p class="notice">购买时间：${new Date(game.purchased_at).toLocaleString()}</p>
      <a class="btn" href="/game/${game.game_id}">查看详情</a>
    `;
    grid.appendChild(card);
  });
}

async function init() {
  const resolved = await resolveUserId();
  if (!resolved) {
    document.getElementById("profile-card").innerHTML =
      '<p class="notice">请先登录后查看个人主页。</p>';
    return;
  }
  const profile = await fetchJson(`/api/users/${resolved}/profile`);
  if (profile.error) {
    document.getElementById("profile-card").innerHTML =
      `<p class="notice">${profile.error}</p>`;
    return;
  }
  renderProfile(profile);
  renderOwnedGames(profile.owned_games);
  renderFriendAction(profile);
}

init();
