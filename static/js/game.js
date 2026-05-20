const container = document.getElementById("game-container");
let gameId = Number(container?.dataset?.gameId || 0);
function showPurchaseStatus(message, type) {
    const purchaseMsg = document.getElementById("purchase-msg");
    if (!purchaseMsg) return;
    purchaseMsg.textContent = message || "";
    purchaseMsg.classList.remove("status-success", "status-error");
    if (type === "success") {
        purchaseMsg.classList.add("status-success");
    }
    if (type === "error") {
        purchaseMsg.classList.add("status-error");
    }
}

if (!gameId) {
    const match = window.location.pathname.match(/\/game\/(\d+)/);
    if (match) {
        gameId = Number(match[1]);
    }
}

async function fetchJson(url, options = {}) {
    const res = await fetch(url, { credentials: "include", cache: "no-store", ...options });
    return res.json();
}


function renderInfo(game) {
    const info = document.getElementById("game-info");
    info.innerHTML = `
    <div class="game-detail-row">
      <div class="game-detail-left">
        <div class="card game-detail-cover">
          <img src="${game.cover_url}" alt="${game.title}" />
        </div>
        <div class="card game-detail-meta">
          <h2 class="game-detail-title">${game.title}</h2>
          <span class="badge game-detail-badge">${game.steam_status}</span>
          <div class="game-detail-price">￥${game.price}</div>
          <div class="game-detail-rating">评分：${game.avg_rating}（${game.review_count}条评价）</div>
        </div>
      </div>
      <div class="card game-detail-video">
        <video class="video" src="${game.video_url}" controls></video>
      </div>
    </div>
  `;
}



async function renderPurchase() {
    const status = await fetchJson(`/api/game/${gameId}/purchase-status`);
    const section = document.getElementById("purchase-section");
    if (status.purchased) {
        section.innerHTML = `
            <p class="notice" id="purchase-msg"></p>
            <div class="title">已拥有</div>
            <div class="subtitle">点击下载即可获取安装包</div>
            <button class="btn" id="download-btn">下载游戏</button>
    `;
        document.getElementById("download-btn").addEventListener("click", () => {
            window.location.href = `/api/game/${gameId}/download`;
        });
        document.getElementById("review-section").style.display = "block";
        showPurchaseStatus("", "");
    } else {
        section.innerHTML = `
            <p class="notice" id="purchase-msg"></p>
            <div class="title">立即购买</div>
            <div class="subtitle">购买后可下载并发表评价</div>
            <button class="btn" id="buy-btn">购买游戏</button>
    `;
        document.getElementById("buy-btn").addEventListener("click", async () => {
            // Check balance first
            const me = await fetchJson("/api/me");
            if (!me.logged_in) {
                showPurchaseStatus("请先登录", "error");
                return;
            }
            const profile = await fetchJson(`/api/users/${me.user_id}/profile`);
            const game = await fetchJson(`/api/game/${gameId}`);
            const balance = profile.balance;
            const price = parseFloat(game.price);

            if (balance < price) {
                // Show custom insufficient balance modal
                const overlay = document.createElement("div");
                overlay.className = "success-overlay";
                overlay.innerHTML = `
                    <div class="confirm-modal">
                        <div class="confirm-title">余额不足</div>
                        <div class="confirm-amount" style="font-size:18px;color:var(--text-bright);margin-bottom:8px;">
                            当前余额：<span style="color:var(--btn-green-text);">￥${balance.toFixed(2)}</span>
                        </div>
                        <div class="confirm-amount" style="font-size:18px;color:var(--text-bright);margin-bottom:24px;">
                            游戏价格：<span style="color:#fca5a5;">￥${price.toFixed(2)}</span>
                        </div>
                        <div class="confirm-actions">
                            <a class="btn" href="/profile">去充值</a>
                            <button class="btn secondary" id="balance-close">关闭</button>
                        </div>
                    </div>
                `;
                document.body.appendChild(overlay);
                overlay.style.display = "flex";
                document.getElementById("balance-close").addEventListener("click", () => {
                    overlay.remove();
                });
                return;
            }

            const result = await fetchJson("/api/purchase", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ game_id: Number(gameId) }),
            });
            if (result.error) {
                showPurchaseStatus(`购买失败：${result.error}`, "error");
                return;
            }
            showPurchaseStatus("购买成功！", "success");
            await renderPurchase();
            await loadReviews();
        });
    }
}


const reviewForm = document.getElementById("review-form");
const reviewList = document.getElementById("review-list");
const reviewEmpty = document.getElementById("review-empty");
reviewForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const msg = document.getElementById("review-msg");
    const formData = new FormData(reviewForm);
    const payload = Object.fromEntries(formData.entries());
    payload.game_id = Number(gameId);
    payload.rating = Number(payload.rating);

    const result = await fetchJson("/api/review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
    if (result.error) {
        msg.textContent = `提交失败：${result.error}`;
        return;
    }
    msg.textContent = "评价已提交";
    await loadReviews();
});

async function loadReviews() {
    if (!reviewList) return;
    const reviews = await fetchJson(`/api/game/${gameId}/reviews?ts=${Date.now()}`);
    reviewList.innerHTML = "";
    if (!Array.isArray(reviews) || reviews.length === 0) {
        if (reviewEmpty) reviewEmpty.textContent = "暂无评价，快来抢沙发！";
        return;
    }
    if (reviewEmpty) reviewEmpty.textContent = "";

    reviews.forEach((review) => {
        const card = document.createElement("div");
        card.className = "review-card";
        const replies = (review.replies || [])
            .map((reply) => {
                const avatar = reply.avatar_url
                    ? `<a href="/profile/${reply.user_id}"><img class="reply-avatar" src="${reply.avatar_url}" alt="${reply.username}" /></a>`
                    : "";
                return `<div class="reply-item">${avatar}<span><strong>${reply.username}</strong> 回复 <strong>${reply.reply_to_username}</strong>：${reply.content}</span> <button class="btn secondary" data-action="reply" data-review-id="${review.review_id}" data-reply-to-id="${reply.user_id}" data-reply-to-name="${reply.username}">回复</button></div>`;
            })
            .join("");

        const authorAvatar = review.avatar_url
            ? `<a href="/profile/${review.user_id}"><img class="reply-avatar" src="${review.avatar_url}" alt="${review.username}" /></a>`
            : "";
        card.innerHTML = `
                    <div class="review-header">
                        <span>${authorAvatar}<strong>${review.username}</strong> · ${review.rating} 星</span>
                        <span>${new Date(review.created_at).toLocaleString()}</span>
                    </div>
                    <p>${review.content}</p>
                    <div class="reply-list">${replies}</div>
                    <div class="reply-form" data-review-id="${review.review_id}" data-reply-to-id="${review.user_id}" data-reply-to-name="${review.username}">
                        <input type="text" placeholder="回复${review.username}的评论" />
                        <button class="btn secondary" data-action="send-reply">发送回复</button>
                    </div>
                `;
        reviewList.appendChild(card);
    });
}

reviewList?.addEventListener("click", async (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    const action = target.dataset.action;
    if (action === "reply") {
        const reviewId = target.dataset.reviewId;
        const replyToId = target.dataset.replyToId;
        const replyToName = target.dataset.replyToName;
        const form = reviewList.querySelector(
            `.reply-form[data-review-id="${reviewId}"]`
        );
        if (form) {
            form.dataset.replyToId = replyToId || "";
            form.dataset.replyToName = replyToName || "";
            const input = form.querySelector("input");
            if (input) {
                input.placeholder = `回复${replyToName}的评论`;
                input.focus();
            }
        }
    }
    if (action === "send-reply") {
        const form = target.closest(".reply-form");
        if (!form) return;
        const input = form.querySelector("input");
        if (!input || !input.value.trim()) return;
        const payload = {
            review_id: Number(form.dataset.reviewId),
            reply_to_user_id: Number(form.dataset.replyToId),
            content: input.value.trim(),
        };
        const result = await fetchJson("/api/review-replies", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        if (result.error) {
            return;
        }
        input.value = "";
        await loadReviews();
    }
});

async function init() {
    try {
        if (!gameId) {
            const match = window.location.pathname.match(/\/game\/(\d+)/);
            if (match) {
                gameId = Number(match[1]);
            }
        }
        if (!gameId) {
            const info = document.getElementById("game-info");
            if (info) info.textContent = "游戏不存在";
            return;
        }
        let game = await fetchJson(`/api/game/${gameId}`);
        if (game.error) {
            const match = window.location.pathname.match(/\/game\/(\d+)/);
            if (match) {
                gameId = Number(match[1]);
                game = await fetchJson(`/api/game/${gameId}`);
            }
        }
        if (game.error) {
            const info = document.getElementById("game-info");
            if (info) info.textContent = "游戏不存在";
            return;
        }
        renderInfo(game);
        await renderPurchase();
        await loadReviews();
    } catch (err) {
        console.error("Game init error:", err);
        const info = document.getElementById("game-info");
        if (info) info.textContent = "加载失败，请稍后重试";
    }
}

init();
