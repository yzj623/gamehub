const grid = document.getElementById("game-grid");
const statusEl = document.getElementById("status");
const adTrack = document.getElementById("ad-track");
const adSection = document.getElementById("ad-section");
const rankSection = document.getElementById("rank-section");
let adScrollIndex = 0;
let adIntervalId;

const buttons = {
    all: document.getElementById("btn-all"),
    top: document.getElementById("btn-top"),
    selling: document.getElementById("btn-selling"),
    priceAsc: document.getElementById("btn-price-asc"),
    priceDesc: document.getElementById("btn-price-desc"),
};


function setActiveButton(activeKey) {
    Object.entries(buttons).forEach(([key, button]) => {
        if (!button) return;
        button.classList.toggle("active", key === activeKey);
        button.classList.toggle("secondary", key !== activeKey);
    });
}

async function loadGames(url, activeKey) {
    statusEl.textContent = "加载中...";
    setActiveButton(activeKey);
    try {
        const res = await fetch(url, { credentials: "include" });
        const data = await res.json();
        grid.innerHTML = "";

        if (!Array.isArray(data) || data.length === 0) {
            const isSearching = adSection && adSection.style.display === "none";
            statusEl.textContent = isSearching ? "暂无相关游戏" : "暂无游戏数据";
            return;
        }

        statusEl.textContent = "";
        data.forEach((game) => {
            const card = document.createElement("div");
            card.className = "card";
            const extraInfo = game.sales_count !== undefined
                ? `<p>🔥 已售 ${game.sales_count} 份</p>`
                : "";
            card.innerHTML = `
      <img src="${game.cover_url}" alt="${game.title}" />
      <h3>${game.title}</h3>
      <p class="game-price">💰 ￥${game.price}</p>
      <p class="game-rating">⭐ ${game.avg_rating}（${game.review_count}条）</p>
      ${extraInfo}
      <a class="btn" href="/game/${game.game_id}">查看详情</a>
    `;
            grid.appendChild(card);
        });
    } catch (err) {
        statusEl.textContent = "加载失败，请稍后重试";
    }
}

buttons.all.addEventListener("click", () => {
    loadGames("/api/games", "all");
});

buttons.top.addEventListener("click", () => {
    loadGames("/api/top-rated", "top");
});

buttons.priceAsc.addEventListener("click", () => {
    loadGames("/api/games-by-price?desc=0", "priceAsc");
});

buttons.selling.addEventListener("click", () => {
    loadGames("/api/top-selling", "selling");
});

buttons.priceDesc.addEventListener("click", () => {
    loadGames("/api/games-by-price?desc=1", "priceDesc");
});

loadGames("/api/games", "all");

// ===== Search =====
const searchInput = document.getElementById("search-input");
const searchBtn = document.getElementById("search-btn");

function setSearchMode(isSearching) {
    if (isSearching) {
        adSection.style.display = "none";
        rankSection.style.display = "none";
    } else {
        adSection.style.display = "";
        rankSection.style.display = "";
    }
}

async function doSearch() {
    const keyword = searchInput.value.trim();
    if (!keyword) {
        setSearchMode(false);
        loadGames("/api/games", "all");
        return;
    }
    setSearchMode(true);
    loadGames(`/api/games?q=${encodeURIComponent(keyword)}`, "all");
}

searchBtn.addEventListener("click", doSearch);
searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        doSearch();
    }
});


async function loadAds() {

    if (!adTrack) return;
    const res = await fetch(`/api/ads?ts=${Date.now()}`, {
        credentials: "include",
        cache: "no-store",
    });
    const ads = await res.json();
    adTrack.innerHTML = "";

    if (!Array.isArray(ads) || ads.length === 0) {
        adTrack.innerHTML = '<div class="notice">暂无广告</div>';
        return;
    }

    ads.forEach((ad) => {
        const card = document.createElement("div");
        card.className = "ad-card";
        const heroImage = (ad.image_urls || [])[0] || "";
        card.innerHTML = `
            <img class="ad-hero" src="${heroImage}" alt="${ad.ad_title}" />
            <div class="ad-content">
                <div>
                    <div class="title">${ad.ad_title}</div>
                    <div class="subtitle">${ad.ad_content}</div>
                </div>
                <div class="ad-footer">
                    <span>${ad.game_title} · ￥${ad.price}</span>
                    <a class="btn" href="/game/${ad.game_id}">查看游戏</a>
                </div>
            </div>
    `;
        adTrack.appendChild(card);
    });

    adScrollIndex = 0;
    updateAdPosition();
}

function updateAdPosition() {
    if (!adTrack) return;
    const cards = adTrack.children;
    if (!cards.length) return;
    const cardWidth = cards[0].getBoundingClientRect().width;
    const offset = cardWidth * adScrollIndex;
    adTrack.style.transform = `translateX(-${offset}px)`;
}

function startAdScroll() {
    if (!adTrack) return;
    if (adIntervalId) {
        clearInterval(adIntervalId);
    }
    adIntervalId = setInterval(() => {
        const cards = adTrack.children;
        if (!cards.length) return;
        adScrollIndex = (adScrollIndex + 1) % cards.length;
        updateAdPosition();
    }, 3500);
}

window.addEventListener("resize", updateAdPosition);
window.addEventListener("pageshow", () => {
    loadAds().then(startAdScroll);
});

loadAds().then(startAdScroll);
