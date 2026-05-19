async function postJson(url, payload) {
    const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(payload),
    });
    return res.json();
}

async function postForm(url, formData) {
    const res = await fetch(url, {
        method: "POST",
        credentials: "include",
        body: formData,
    });
    const data = await res.json();
    return { ok: res.ok, data };
}

const loginForm = document.getElementById("login-form");
if (loginForm) {
    loginForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const formData = new FormData(loginForm);
        const payload = Object.fromEntries(formData.entries());
        const result = await postJson("/api/login", payload);
        const msg = document.getElementById("login-msg");
        if (result.error) {
            msg.textContent = `登录失败：${result.error}`;
            return;
        }
        msg.textContent = "登录成功，正在跳转...";
        if (result.role === "publisher") {
            window.location.href = "/publisher";
        } else {
            window.location.href = "/";
        }
    });
}

const registerForm = document.getElementById("register-form");
if (registerForm) {
    registerForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const formData = new FormData(registerForm);
        const submitBtn = registerForm.querySelector("button[type='submit']");
        const msg = document.getElementById("register-msg");
        if (submitBtn) submitBtn.disabled = true;
        msg.textContent = "注册中...";
        try {
            const result = await postForm("/api/register", formData);
            if (!result.ok || result.data.error) {
                msg.textContent = `注册失败：${result.data.error || "未知错误"}`;
                msg.classList.add("status-error");
                return;
            }
            msg.textContent = "注册成功，正在跳转登录...";
            msg.classList.remove("status-error");
            msg.classList.add("status-success");
            setTimeout(() => {
                window.location.href = "/login";
            }, 800);
        } catch (err) {
            msg.textContent = "注册失败：网络异常";
            msg.classList.add("status-error");
        } finally {
            if (submitBtn) submitBtn.disabled = false;
        }
    });
}
