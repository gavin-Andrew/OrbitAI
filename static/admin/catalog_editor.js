const editorDataElement = document.getElementById("catalogEditorData");
const editorData = JSON.parse(editorDataElement.textContent);
const entities = editorData.entities;

const elements = {
    entityList: document.getElementById("entityList"),
    search: document.getElementById("entitySearch"),
    form: document.getElementById("catalogEditForm"),
    entityType: document.getElementById("entityType"),
    entityId: document.getElementById("entityId"),
    expectedRevision: document.getElementById("expectedRevision"),
    stableId: document.getElementById("stableId"),
    name: document.getElementById("entityName"),
    organizationType: document.getElementById("organizationType"),
    homepageUrl: document.getElementById("homepageUrl"),
    status: document.getElementById("entityStatus"),
    aliases: document.getElementById("entityAliases"),
    description: document.getElementById("entityDescription"),
    changeReason: document.getElementById("changeReason"),
    organizationTypeField: document.getElementById("organizationTypeField"),
    homepageField: document.getElementById("homepageField"),
    selectedType: document.getElementById("selectedEntityType"),
    selectedName: document.getElementById("selectedEntityName"),
    selectedStatus: document.getElementById("selectedEntityStatus"),
    previewButton: document.getElementById("previewButton"),
    saveButton: document.getElementById("saveButton"),
    result: document.getElementById("editResult"),
    changeLog: document.getElementById("changeLog"),
};

let selectedIndex = -1;
let previewApproved = false;

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function getStatusLabel(entityType, value) {
    const option = editorData.options.statuses[entityType]
        .find((item) => item.value === value);
    return option ? option.label : value;
}

function renderEntityList() {
    const query = elements.search.value.trim().toLocaleLowerCase();
    const filtered = entities
        .map((entity, index) => ({ entity, index }))
        .filter(({ entity }) => {
            const text = `${entity.name} ${entity.entity_id} ${entity.aliases.join(" ")}`;
            return text.toLocaleLowerCase().includes(query);
        });

    const groups = [
        { type: "organization", label: "组织" },
        { type: "person", label: "人物" },
    ];

    elements.entityList.innerHTML = groups.map((group) => {
        const items = filtered.filter(({ entity }) => entity.entity_type === group.type);
        if (items.length === 0) {
            return "";
        }
        return `
            <section class="catalog-entity-group">
                <h3>${group.label}<span>${items.length}</span></h3>
                ${items.map(({ entity, index }) => `
                    <button type="button"
                            class="catalog-entity-item ${index === selectedIndex ? "is-active" : ""}"
                            data-entity-index="${index}">
                        <strong>${escapeHtml(entity.name)}</strong>
                        <span>${escapeHtml(entity.entity_id)} · ${escapeHtml(getStatusLabel(entity.entity_type, entity.status))}</span>
                    </button>
                `).join("")}
            </section>
        `;
    }).join("") || '<p class="catalog-no-result">没有匹配的档案。</p>';

    elements.entityList.querySelectorAll("[data-entity-index]").forEach((button) => {
        button.addEventListener("click", () => selectEntity(Number(button.dataset.entityIndex)));
    });
}

function fillSelect(select, options, selectedValue) {
    select.innerHTML = options.map((option) => `
        <option value="${escapeHtml(option.value)}" ${option.value === selectedValue ? "selected" : ""}>
            ${escapeHtml(option.label)}
        </option>
    `).join("");
}

function selectEntity(index) {
    selectedIndex = index;
    previewApproved = false;
    const entity = entities[index];
    const isOrganization = entity.entity_type === "organization";

    elements.entityType.value = entity.entity_type;
    elements.entityId.value = entity.entity_id;
    elements.expectedRevision.value = entity.revision;
    elements.stableId.value = entity.entity_id;
    elements.name.value = entity.name;
    elements.description.value = entity.description || "";
    elements.aliases.value = entity.aliases.join("\n");
    elements.changeReason.value = "";
    elements.selectedType.textContent = entity.type_label;
    elements.selectedName.textContent = entity.name;
    elements.selectedStatus.textContent = entity.status_label;
    elements.selectedStatus.dataset.status = entity.status;

    fillSelect(
        elements.status,
        editorData.options.statuses[entity.entity_type],
        entity.status,
    );
    elements.organizationTypeField.hidden = !isOrganization;
    elements.homepageField.hidden = !isOrganization;
    if (isOrganization) {
        fillSelect(
            elements.organizationType,
            editorData.options.organization_types,
            entity.organization_type,
        );
        elements.homepageUrl.value = entity.homepage_url || "";
    } else {
        elements.organizationType.innerHTML = "";
        elements.homepageUrl.value = "";
    }

    elements.previewButton.disabled = false;
    elements.saveButton.disabled = true;
    elements.result.className = "catalog-edit-result";
    elements.result.innerHTML = "<p>可以修改字段。数据库尚未发生变化。</p>";
    renderEntityList();
}

function buildPayload(includeReason = false) {
    const entityType = elements.entityType.value;
    const values = {
        name: elements.name.value,
        description: elements.description.value,
        status: elements.status.value,
        aliases: elements.aliases.value
            .split(/\r?\n/)
            .map((value) => value.trim())
            .filter(Boolean),
    };
    if (entityType === "organization") {
        values.organization_type = elements.organizationType.value;
        values.homepage_url = elements.homepageUrl.value;
    }

    const payload = {
        entity_type: entityType,
        entity_id: elements.entityId.value,
        expected_revision: elements.expectedRevision.value,
        values,
    };
    if (includeReason) {
        payload.change_reason = elements.changeReason.value;
    }
    return payload;
}

function formatValue(value) {
    if (Array.isArray(value)) {
        return value.length ? value.join("、") : "（空）";
    }
    if (value === null || value === "") {
        return "（空）";
    }
    return String(value);
}

function renderPreview(preview) {
    const changes = Object.values(preview.changes);
    if (changes.length === 0) {
        elements.result.className = "catalog-edit-result is-neutral";
        elements.result.innerHTML = "<strong>没有变化</strong><p>当前表单与数据库内容相同，不需要保存。</p>";
        elements.saveButton.disabled = true;
        previewApproved = false;
        return;
    }

    elements.result.className = "catalog-edit-result is-ready";
    elements.result.innerHTML = `
        <strong>预览通过：${changes.length} 个字段将被修改</strong>
        <div class="catalog-diff-list">
            ${changes.map((change) => `
                <article>
                    <h3>${escapeHtml(change.label)}</h3>
                    <p><span>修改前</span>${escapeHtml(formatValue(change.before))}</p>
                    <p><span>修改后</span>${escapeHtml(formatValue(change.after))}</p>
                </article>
            `).join("")}
        </div>
        <p>数据库仍未修改。填写修改原因后，才可以执行事务保存。</p>
    `;
    previewApproved = true;
    elements.saveButton.disabled = false;
}

function renderError(data, responseStatus) {
    previewApproved = false;
    elements.saveButton.disabled = true;
    const errors = Array.isArray(data.errors) ? data.errors : [data.message || "未知错误"];
    elements.result.className = `catalog-edit-result ${responseStatus === 409 ? "is-conflict" : "is-error"}`;
    elements.result.innerHTML = `
        <strong>${responseStatus === 409 ? "检测到并发冲突" : "未通过校验"}</strong>
        <ul>${errors.map((error) => `<li>${escapeHtml(error)}</li>`).join("")}</ul>
        ${responseStatus === 409 ? "<p>数据库中已有更新。请刷新页面，重新阅读最新内容后再编辑。</p>" : ""}
    `;
}

async function requestJson(url, payload) {
    const response = await fetch(url, {
        method: "POST",
        headers: {
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
    });
    let data;
    try {
        data = await response.json();
    } catch (_error) {
        data = { message: "服务器返回了无法读取的结果。" };
    }
    return { response, data };
}

async function previewEdit() {
    elements.previewButton.disabled = true;
    elements.saveButton.disabled = true;
    elements.result.className = "catalog-edit-result is-loading";
    elements.result.innerHTML = "<p>正在读取最新数据库状态并检查冲突……</p>";

    const { response, data } = await requestJson(
        "/admin/catalog/preview",
        buildPayload(false),
    );
    elements.previewButton.disabled = false;
    if (!response.ok) {
        renderError(data, response.status);
        return;
    }
    renderPreview(data.preview);
}

function prependChangeLog(result, reason) {
    const empty = elements.changeLog.querySelector(".catalog-empty-log");
    if (empty) {
        empty.remove();
    }
    const article = document.createElement("article");
    article.innerHTML = `
        <div>
            <strong>${escapeHtml(result.entity.name)}</strong>
            <span>${escapeHtml(result.entity.type_label)} · ${escapeHtml(result.action)} · #${result.log_id}</span>
        </div>
        <p>${escapeHtml(reason)}</p>
        <small>刚刚保存 · 修改 ${Object.keys(result.changes).length} 个字段</small>
    `;
    elements.changeLog.prepend(article);
}

async function saveEdit() {
    if (!previewApproved) {
        return;
    }
    const reason = elements.changeReason.value.trim();
    if (reason.length < 3) {
        elements.result.className = "catalog-edit-result is-error";
        elements.result.innerHTML = "<strong>还不能保存</strong><p>请填写至少 3 个字符的修改原因。</p>";
        return;
    }

    elements.previewButton.disabled = true;
    elements.saveButton.disabled = true;
    elements.result.className = "catalog-edit-result is-loading";
    elements.result.innerHTML = "<p>正在重新检查冲突，并保存业务数据与修改记录……</p>";

    const payload = buildPayload(true);
    const { response, data } = await requestJson("/admin/catalog/save", payload);
    if (!response.ok) {
        elements.previewButton.disabled = false;
        renderError(data, response.status);
        return;
    }

    entities[selectedIndex] = data.entity;
    prependChangeLog(data, reason);
    selectEntity(selectedIndex);
    elements.result.className = "catalog-edit-result is-success";
    elements.result.innerHTML = `
        <strong>保存成功</strong>
        <p>业务修改与修改记录 #${data.log_id} 已经在同一个事务中提交。</p>
    `;
}

const contentFields = [
    elements.name,
    elements.organizationType,
    elements.homepageUrl,
    elements.status,
    elements.aliases,
    elements.description,
];
contentFields.forEach((field) => {
    ["input", "change"].forEach((eventName) => {
        field.addEventListener(eventName, () => {
            if (selectedIndex < 0) {
                return;
            }
            previewApproved = false;
            elements.saveButton.disabled = true;
            elements.result.className = "catalog-edit-result";
            elements.result.innerHTML = "<p>表单已经变化，请重新预览后再保存。</p>";
        });
    });
});

elements.form.addEventListener("submit", (event) => event.preventDefault());
elements.search.addEventListener("input", renderEntityList);
elements.previewButton.addEventListener("click", previewEdit);
elements.saveButton.addEventListener("click", saveEdit);

renderEntityList();
if (entities.length > 0) {
    selectEntity(0);
}
