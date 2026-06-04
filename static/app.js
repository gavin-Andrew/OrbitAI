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
