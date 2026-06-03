const searchInput = document.getElementById("searchInput");
const sourceFilter = document.getElementById("sourceFilter");
const categoryFilter = document.getElementById("categoryFilter");
const tagFilter = document.getElementById("tagFilter");
const resultCount = document.getElementById("resultCount");
const cards = Array.from(document.querySelectorAll(".card"));

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

        const shouldShow = matchesSearch && matchesSource && matchesCategory && matchesTag;

        card.style.display = shouldShow ? "block" : "none";

        if (shouldShow) {
            visibleCount += 1;
        }
    });

    resultCount.textContent = `当前显示：${visibleCount} / ${cards.length} 条`;
}

if (searchInput && sourceFilter && categoryFilter && tagFilter) {
    searchInput.addEventListener("input", updateCards);
    sourceFilter.addEventListener("change", updateCards);
    categoryFilter.addEventListener("change", updateCards);
    tagFilter.addEventListener("change", updateCards);

    updateCards();
}
