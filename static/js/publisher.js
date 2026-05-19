const publishForm = document.getElementById("publish-form");
const roleHint = document.getElementById("role-hint");
const adForm = document.getElementById("ad-form");
const adGameSelect = document.getElementById("ad-game");
const mailForm = document.getElementById("mail-form");
const mailGameSelect = document.getElementById("mail-game");
let adMsgTimer;

function setFormDisabled(form, disabled) {
    if (!form) return;
    form.querySelectorAll("input, textarea, select, button").forEach((el) => {
        el.disabled = disabled;
    });
}

async function checkRole() {
    const res = await fetch("/api/me", { credentials: "include" });
    const info = await res.json();
    if (!info.logged_in) {
        roleHint.textContent = "请先登录发行商账号后再上架游戏。";
        setFormDisabled(publishForm, true);
        setFormDisabled(adForm, true);
        setFormDisabled(mailForm, true);
        return false;
    }
    if (info.role !== "publisher") {
        roleHint.textContent = "当前账号不是发行商，无法上架游戏。";
        setFormDisabled(publishForm, true);
        setFormDisabled(adForm, true);
        setFormDisabled(mailForm, true);
        return false;
    }
    roleHint.textContent = "";
    setFormDisabled(publishForm, false);
    setFormDisabled(adForm, false);
    setFormDisabled(mailForm, false);
    return true;
}

function showStatus(element, message, type) {
    if (!element) return;
    element.textContent = message;
    element.classList.remove("status-success", "status-error");
    if (type === "success") {
        element.classList.add("status-success");
    }
    if (type === "error") {
        element.classList.add("status-error");
    }
    if (adMsgTimer) {
        clearTimeout(adMsgTimer);
    }
    if (type === "success") {
        adMsgTimer = setTimeout(() => {
            element.textContent = "";
            element.classList.remove("status-success");
        }, 2200);
    }
}

function fillGameOptions(select, games) {
    if (!select) return;
    select.innerHTML = '<option value="">请选择游戏</option>';
    games.forEach((game) => {
        const option = document.createElement("option");
        option.value = game.game_id;
        option.textContent = `${game.title}（￥${game.price}）`;
        select.appendChild(option);
    });
}

async function loadMyGames() {
    if (!adGameSelect && !mailGameSelect) return;
    const res = await fetch("/api/publisher/my-games", { credentials: "include" });
    const games = await res.json();
    if (!Array.isArray(games)) {
        return;
    }
    fillGameOptions(adGameSelect, games);
    fillGameOptions(mailGameSelect, games);
}

if (publishForm) {
    publishForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!(await checkRole())) {
            return;
        }
        const msg = document.getElementById("publish-msg");
        showStatus(msg, "上传中...", "");

        const formData = new FormData(publishForm);
        try {
            const controller = new AbortController();
            const timer = setTimeout(() => controller.abort(), 10000);
            const res = await fetch("/api/publisher/games", {
                method: "POST",
                credentials: "include",
                body: formData,
                signal: controller.signal,
            });
            clearTimeout(timer);
            const result = await res.json();
            if (!res.ok || result.error) {
                showStatus(msg, `上架失败：${result.error || res.statusText}`, "error");
                return;
            }
            showStatus(msg, "上架成功！", "success");
            publishForm.reset();
            await loadMyGames();
        } catch (err) {
            showStatus(msg, "上架失败：网络异常", "error");
        }
    });
}

if (adForm) {
    adForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!(await checkRole())) {
            return;
        }
        const msg = document.getElementById("ad-msg");
        showStatus(msg, "发布中...", "");

        const formData = new FormData(adForm);
        const images = adForm.querySelector('input[name="images"]').files;
        if (images.length === 0 || images.length > 4) {
            showStatus(msg, "请上传 1-4 张图片", "error");
            return;
        }
        try {
            const controller = new AbortController();
            const timer = setTimeout(() => controller.abort(), 10000);
            const res = await fetch("/api/publisher/ads", {
                method: "POST",
                credentials: "include",
                body: formData,
                signal: controller.signal,
            });
            clearTimeout(timer);
            const result = await res.json();
            if (!res.ok || result.error) {
                showStatus(msg, `发布失败：${result.error || res.statusText}`, "error");
                return;
            }
            showStatus(msg, "广告发布成功！", "success");
            adForm.reset();
        } catch (err) {
            showStatus(msg, "发布失败：网络异常", "error");
        }
    });
}

if (mailForm) {
    mailForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!(await checkRole())) {
            return;
        }
        const msg = document.getElementById("mail-msg");
        showStatus(msg, "发送中...", "");

        const contentField = mailForm.querySelector('textarea[name="content"]');
        const imageField = mailForm.querySelector('input[name="image"]');
        const content = contentField ? contentField.value.trim() : "";
        const image = imageField ? imageField.files[0] : null;

        if (content && image) {
            showStatus(msg, "文字和图片只能二选一", "error");
            return;
        }
        if (!content && !image) {
            showStatus(msg, "请填写文字或选择图片", "error");
            return;
        }
        const formData = new FormData(mailForm);
        try {
            const controller = new AbortController();
            const timer = setTimeout(() => controller.abort(), 10000);
            const res = await fetch("/api/publisher/mail", {
                method: "POST",
                credentials: "include",
                body: formData,
                signal: controller.signal,
            });
            clearTimeout(timer);
            const result = await res.json();
            if (!res.ok || result.error) {
                showStatus(msg, `发送失败：${result.error || res.statusText}`, "error");
                return;
            }
            showStatus(msg, `已发送给 ${result.count || 0} 位玩家`, "success");
            mailForm.reset();
        } catch (err) {
            console.error("Mail send error:", err);
            showStatus(msg, `发送失败：${err.message || "网络异常"}`, "error");
        }
    });
}

checkRole().then(loadMyGames);
