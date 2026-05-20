async function fetchJson(url, options = {}) {
    const res = await fetch(url, { credentials: "include", ...options });
    const contentType = res.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) {
        const text = await res.text();
        throw new Error(`服务器返回了非 JSON 响应 (${res.status}): ${text.slice(0, 100)}`);
    }
    const data = await res.json();
    if (!res.ok) {
        throw new Error(data.error || `请求失败 (${res.status})`);
    }
    return data;
}

async function getSessionInfo() {
    try {
        return await fetchJson("/api/me");
    } catch (err) {
        return { logged_in: false };
    }
}

function closePanels() {
    document.querySelectorAll(".nav-panel.active").forEach((panel) => {
        panel.classList.remove("active");
    });
}

async function loadMail() {
    const list = document.getElementById("mail-list");
    const empty = document.getElementById("mail-empty");
    if (!list || !empty) return;
    const mails = await fetchJson("/api/mail");
    list.innerHTML = "";
    if (!Array.isArray(mails) || mails.length === 0) {
        empty.textContent = "暂无邮件";
        return;
    }
    empty.textContent = "";
    mails.forEach((mail) => {
        const item = document.createElement("div");
        item.className = "friend-item";
        item.style.cursor = "pointer";
        const timeText = mail.created_at ? new Date(mail.created_at).toLocaleString() : "";
        const preview = mail.content ? mail.content.slice(0, 15) + (mail.content.length > 15 ? "..." : "") : (mail.image_url ? "[图片]" : "");
        item.innerHTML = `
            <img class="friend-avatar" src="${mail.from_avatar_url}" alt="${mail.from_username}" />
            <div style="flex:1;min-width:0;">
                <div><strong>${mail.from_username}</strong></div>
                <div class="notice" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${preview}</div>
                <div class="notice" style="font-size:0.75em;">${timeText}</div>
            </div>
        `;
        item.addEventListener("click", () => {
            window.location.href = `/mail/${mail.mail_id}`;
        });
        list.appendChild(item);
    });
}

async function loadFriendRequests() {
    const list = document.getElementById("mail-friend-requests");
    const empty = document.getElementById("mail-request-empty");
    if (!list || !empty) return;
    const requests = await fetchJson("/api/friends/requests");
    list.innerHTML = "";
    if (!Array.isArray(requests) || requests.length === 0) {
        empty.textContent = "暂无好友申请";
        return;
    }
    empty.textContent = "";
    requests.forEach((req) => {
        const item = document.createElement("div");
        item.className = "friend-item";
        item.innerHTML = `
            <img class="friend-avatar" src="${req.avatar_url}" alt="${req.from_username}" />
            <div style="flex:1;">
                <div><strong>${req.from_username}</strong></div>
                <div class="notice">${req.message || "想成为你的好友"}</div>
            </div>
            <div class="friend-actions">
                <button class="btn" data-action="accept" data-id="${req.request_id}">通过</button>
                <button class="btn secondary" data-action="reject" data-id="${req.request_id}">拒绝</button>
            </div>
        `;
        list.appendChild(item);
    });
}

async function loadFriends() {
    const list = document.getElementById("nav-friend-list");
    const empty = document.getElementById("nav-friend-empty");
    if (!list || !empty) return;
    const friends = await fetchJson("/api/friends");
    list.innerHTML = "";
    if (!Array.isArray(friends) || friends.length === 0) {
        empty.textContent = "暂无好友";
        return;
    }
    empty.textContent = "";
    friends.forEach((friend) => {
        const item = document.createElement("div");
        item.className = "friend-item";
        item.innerHTML = `
            <img class="friend-avatar" src="${friend.avatar_url}" alt="${friend.username}" />
            <div style="flex:1;">
                <div><strong>${friend.username}</strong></div>
            </div>
            <div class="friend-actions">
                <a class="btn secondary" href="/profile/${friend.friend_id}">查看主页</a>
                <a class="btn primary" href="/chat/${friend.friend_id}">私信</a>
            </div>

        `;
        list.appendChild(item);
    });
}

function initFriendSearch() {
    const input = document.getElementById("nav-friend-search");
    const messageInput = document.getElementById("nav-friend-message");
    const button = document.getElementById("nav-friend-search-btn");
    const results = document.getElementById("nav-friend-results");
    if (!input || !messageInput || !button || !results) return;

    button.addEventListener("click", async () => {
        const keyword = input.value.trim();
        if (!keyword) return;
        const users = await fetchJson(`/api/users/search?username=${encodeURIComponent(keyword)}`);
        results.innerHTML = "";
        if (!Array.isArray(users) || users.length === 0) {
            results.innerHTML = '<p class="notice">没有找到用户</p>';
            return;
        }
        users.forEach((user) => {
            const item = document.createElement("div");
            item.className = "friend-item";
            item.innerHTML = `
                <img class="friend-avatar" src="${user.avatar_url}" alt="${user.username}" />
                <div style="flex:1;"><strong>${user.username}</strong></div>
                <div class="friend-actions">
                    <button class="btn secondary" data-action="add" data-id="${user.user_id}">添加好友</button>
                </div>
            `;
            results.appendChild(item);
        });
    });

    results.addEventListener("click", async (event) => {
        const target = event.target;
        if (!(target instanceof HTMLElement)) return;
        if (target.dataset.action !== "add") return;
        const toUserId = Number(target.dataset.id);
        if (!toUserId) return;
        const message = messageInput.value.trim().slice(0, 30);
        const result = await fetchJson("/api/friends/requests", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ to_user_id: toUserId, message }),
        });
        if (!result.error) {
            target.textContent = "已发送";
            target.setAttribute("disabled", "true");
        }
    });
}

async function initNav() {
    const info = await getSessionInfo();
    const loginLink = document.getElementById("nav-login");
    const registerLink = document.getElementById("nav-register");
    const logoutBtn = document.getElementById("nav-logout");
    const publisherLink = document.getElementById("nav-publisher");
    const profileLink = document.getElementById("nav-profile");
    const mailMenu = document.getElementById("nav-mail-menu");
    const mailPanel = document.getElementById("nav-mail-panel");
    const mailBtn = document.getElementById("nav-mail");
    const friendsMenu = document.getElementById("nav-friends-menu");
    const friendsPanel = document.getElementById("nav-friends-panel");
    const friendsBtn = document.getElementById("nav-friends");

    if (!info.logged_in) {
        if (logoutBtn) logoutBtn.style.display = "none";
        if (publisherLink) publisherLink.style.display = "none";
        return;
    }


    if (loginLink) loginLink.style.display = "none";
    if (registerLink) registerLink.style.display = "none";
    if (logoutBtn) logoutBtn.style.display = "inline-block";
    if (profileLink) {
        profileLink.style.display = "inline-block";
        profileLink.setAttribute("href", "/profile");
    }

    if (publisherLink && info.role === "publisher") {
        publisherLink.style.display = "inline-block";
    }


    if (mailMenu) mailMenu.style.display = "inline-block";
    if (friendsMenu) friendsMenu.style.display = "inline-block";

    initFriendSearch();

    if (mailBtn && mailPanel) {
        mailBtn.addEventListener("click", async (event) => {
            event.stopPropagation();
            const nextState = !mailPanel.classList.contains("active");
            closePanels();
            if (nextState) {
                mailPanel.classList.add("active");
                await loadMail();
                await loadFriendRequests();
            }
        });
    }

    if (friendsBtn && friendsPanel) {
        friendsBtn.addEventListener("click", async (event) => {
            event.stopPropagation();
            const nextState = !friendsPanel.classList.contains("active");
            closePanels();
            if (nextState) {
                friendsPanel.classList.add("active");
                await loadFriends();
            }
        });
    }

    if (mailPanel) {
        mailPanel.addEventListener("click", async (event) => {
            const target = event.target;
            if (!(target instanceof HTMLElement)) return;
            const action = target.dataset.action;
            const requestId = target.dataset.id;
            if (!action || !requestId) return;
            await fetchJson(`/api/friends/requests/${requestId}/${action}`, { method: "POST" });
            await loadFriendRequests();
            await loadFriends();
        });
    }

    document.addEventListener("click", (event) => {
        const target = event.target;
        if (!(target instanceof HTMLElement)) return;
        if (target.closest(".nav-menu")) return;
        closePanels();
    });

    if (logoutBtn) {
        logoutBtn.addEventListener("click", async () => {
            await fetchJson("/api/logout", { method: "POST" });
            window.location.href = "/";
        });
    }
}

initNav();
