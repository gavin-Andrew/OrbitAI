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
