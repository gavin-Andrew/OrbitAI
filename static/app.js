const searchInput = document.getElementById("searchInput");
const sourceFilter = document.getElementById("sourceFilter");
const categoryFilter = document.getElementById("categoryFilter");
const tagFilter = document.getElementById("tagFilter");
const sortSelect = document.getElementById("sortSelect");
const resultCount = document.getElementById("resultCount");
const feedList = document.getElementById("feedList");
const cards = Array.from(document.querySelectorAll(".card"));
const quickFilterButtons = Array.from(document.querySelectorAll(".quick-filter"));

let activeQuickFilter = "all";

function matchesQuickFilter(card) {
    if (activeQuickFilter === "today") {
        return card.dataset.today === "true";
    }

    if (activeQuickFilter === "high-score") {
        return card.dataset.highScore === "true";
    }

    if (activeQuickFilter === "unprocessed") {
        return card.dataset.aiComplete !== "true";
    }

    return true;
}

function sortCards() {
    if (!feedList || !sortSelect) {
        return;
    }

    const sortValue = sortSelect.value;
    const sortedCards = [...cards];

    sortedCards.sort((a, b) => {
        const scoreA = Number(a.dataset.score || 0);
        const scoreB = Number(b.dataset.score || 0);
        const timeA = a.dataset.time || "";
        const timeB = b.dataset.time || "";

        if (sortValue === "time-desc") {
            return timeB.localeCompare(timeA);
        }

        if (sortValue === "time-asc") {
            return timeA.localeCompare(timeB);
        }

        if (sortValue === "score-desc") {
            return scoreB - scoreA;
        }

        if (sortValue === "score-asc") {
            return scoreA - scoreB;
        }

        return timeB.localeCompare(timeA);
    });

    sortedCards.forEach((card) => {
        feedList.appendChild(card);
    });
}

function updateCards() {
    if (!searchInput || !sourceFilter || !categoryFilter || !tagFilter || !resultCount) {
        return;
    }

    const searchValue = searchInput.value.trim().toLowerCase();
    const selectedSource = sourceFilter.value;
    const selectedCategory = categoryFilter.value;
    const selectedTag = tagFilter.value;

    let visibleCount = 0;

    cards.forEach((card) => {
        const cardSource = card.dataset.source;
        const cardCategory = card.dataset.category;
        const cardTags = card.dataset.tags || "";
        const cardSearch = card.dataset.search || "";

        const matchesSearch = !searchValue || cardSearch.includes(searchValue);
        const matchesSource = selectedSource === "all" || cardSource === selectedSource;
        const matchesCategory = selectedCategory === "all" || cardCategory === selectedCategory;
        const matchesTag = selectedTag === "all" || cardTags.split("||").includes(selectedTag);
        const matchesQuick = matchesQuickFilter(card);

        const shouldShow = matchesSearch && matchesSource && matchesCategory && matchesTag && matchesQuick;

        card.style.display = shouldShow ? "block" : "none";

        if (shouldShow) {
            visibleCount += 1;
        }
    });

    resultCount.textContent = `当前显示：${visibleCount} / ${cards.length} 条`;
}

function resetFilters() {
    if (searchInput) {
        searchInput.value = "";
    }

    if (sourceFilter) {
        sourceFilter.value = "all";
    }

    if (categoryFilter) {
        categoryFilter.value = "all";
    }

    if (tagFilter) {
        tagFilter.value = "all";
    }
}

if (searchInput && sourceFilter && categoryFilter && tagFilter) {
    searchInput.addEventListener("input", updateCards);
    sourceFilter.addEventListener("change", updateCards);
    categoryFilter.addEventListener("change", updateCards);
    tagFilter.addEventListener("change", updateCards);

    if (sortSelect) {
        sortSelect.addEventListener("change", () => {
            sortCards();
            updateCards();
        });
    }

    quickFilterButtons.forEach((button) => {
        button.addEventListener("click", () => {
            activeQuickFilter = button.dataset.filter || "all";

            quickFilterButtons.forEach((currentButton) => {
                currentButton.classList.toggle("active", currentButton === button);
            });

            updateCards();
        });
    });

    document.querySelectorAll(".detail-toggle").forEach((button) => {
        button.addEventListener("click", () => {
            const card = button.closest(".card");
            const details = card ? card.querySelector(".details") : null;

            if (!details) {
                return;
            }

            const isHidden = details.hasAttribute("hidden");

            if (isHidden) {
                details.removeAttribute("hidden");
                button.textContent = "收起详情";
            } else {
                details.setAttribute("hidden", "");
                button.textContent = "展开详情";
            }
        });
    });

    sortCards();
    updateCards();
}


/* =========================
   OrbitAI V3.6 Admin Controls
   状态页手动操作逻辑
   ========================= */

const adminResult = document.getElementById("adminResult");
const adminButtons = Array.from(document.querySelectorAll("[data-admin-action]"));

function setAdminButtonsDisabled(disabled) {
    adminButtons.forEach((button) => {
        button.disabled = disabled;

        if (disabled) {
            button.classList.add("is-loading");
        } else {
            button.classList.remove("is-loading");
        }
    });
}

function formatAdminResult(data) {
    if (!data) {
        return "没有返回结果。";
    }

    const lines = [];

    lines.push(`状态：${data.ok ? "成功" : "失败"}`);

    if (data.message) {
        lines.push(`消息：${data.message}`);
    }

    if (data.result) {
        const result = data.result;

        if (typeof result.fetched_count !== "undefined") {
            lines.push(`抓取数量：${result.fetched_count}`);
        }

        if (typeof result.inserted_count !== "undefined") {
            lines.push(`写入数量：${result.inserted_count}`);
        }

        if (typeof result.skipped_count !== "undefined") {
            lines.push(`跳过数量：${result.skipped_count}`);
        }

        if (typeof result.requested_count !== "undefined") {
            lines.push(`请求处理：${result.requested_count}`);
        }

        if (typeof result.processed_count !== "undefined") {
            lines.push(`实际处理：${result.processed_count}`);
        }

        if (typeof result.success_count !== "undefined") {
            lines.push(`成功数量：${result.success_count}`);
        }

        if (typeof result.fail_count !== "undefined") {
            lines.push(`失败数量：${result.fail_count}`);
        }

        if (typeof result.total_count !== "undefined") {
            lines.push(`当前总数：${result.total_count}`);
        }

        if (Array.isArray(result.generated_files)) {
            lines.push(`生成文件：${result.generated_files.join("、")}`);
        }
    }

    if (data.status) {
        lines.push("");
        lines.push("最新状态：");
        lines.push(`总文章数：${data.status.total_count}`);
        lines.push(`今日新增：${data.status.today_count}`);
        lines.push(`AI 已处理：${data.status.ai_processed_count}`);
        lines.push(`AI 未处理：${data.status.ai_unprocessed_count}`);
        lines.push(`AI 失败：${data.status.ai_failed_count}`);
    }

    if (data.error) {
        lines.push("");
        lines.push(`错误：${data.error}`);
    }

    lines.push("");
    lines.push("完整返回：");
    lines.push(JSON.stringify(data, null, 2));

    return lines.join("\n");
}

async function runAdminAction(url, actionName) {
    if (!adminResult) {
        return;
    }

    setAdminButtonsDisabled(true);
    adminResult.textContent = `正在执行：${actionName} ...`;

    try {
        const response = await fetch(url, {
            method: "POST",
            headers: {
                "Accept": "application/json",
            },
        });

        const data = await response.json();

        adminResult.textContent = formatAdminResult(data);

        if (!response.ok) {
            console.error("Admin action failed:", data);
        }
    } catch (error) {
        adminResult.textContent = `请求失败：${error}`;
        console.error("Admin request error:", error);
    } finally {
        setAdminButtonsDisabled(false);
    }
}

if (adminButtons.length > 0) {
    adminButtons.forEach((button) => {
        button.addEventListener("click", () => {
            const url = button.dataset.adminAction;
            const actionName = button.dataset.adminName || button.textContent.trim() || "手动操作";

            if (!url) {
                return;
            }

            runAdminAction(url, actionName);
        });
    });
}