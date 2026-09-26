# V4.2 最小事件闭环切片

本文件保留 2026-09-13 至 09-14 首批切片与写入记录。2026-09-16 后续完整交付见 [V4.2 剩余功能规格](V4_2_COMPLETION_SPEC.md) 和[统一验收说明](../guides/V4_2_ACCEPTANCE.md)；下方“本轮不做”只描述首批切片边界。

状态：2026-09-13 用户授权选择小范围研究问题并实现闭环；以下样本为代理策划预览，活动库写入与事件确认分开审核。SpaceXAI 抓取搁置。

## 研究问题与样本完整预览

问题：**库中关于 GPT-5.6 的预览、模型介绍和 Copilot 采用，分别支持什么事件，哪些还不能确认？**

限一个赛道 `general_foundation_models`、一个名册组织 `openai`、三篇库内 RSS 材料。不新增 Microsoft 组织，不自动关联 Sam Altman，不联网补正文或调用 AI。这里的模型名及说法来自现有材料快照，不是本轮独立核实的外部事实。

本轮批次 ID：`gpt56_rss_slice_20260913`。拟新增三个未确认事件、三个 RSS 摘录文档及其关联，不修改 articles 或来源名册。由代理整理的三条事件保留 `origin=ai`，不冒充人工撰写；尚无用户确认事件。用户已于本轮完整预览后明确批准保存未确认样本及备份后执行迁移 0007。

### 1. `event_gpt56_sol_preview`

- 材料 #110：Previewing GPT-5.6 Sol: a next-generation model
- 原始链接：https://openai.com/index/previewing-gpt-5-6-sol
- 库存发布时间：Fri, 26 Jun 2026 10:00:00 GMT
- 库存原文摘录：OpenAI previews GPT-5.6 Sol, a next-generation model with stronger capabilities in coding, science, and cybersecurity, paired with its most advanced safety stack.
- 候选标题：OpenAI 发布 GPT-5.6 Sol 预览公告
- 类型：`model_release`；状态：`candidate`；人工确认：否
- 日期：2026-06-26，`day`；只表示该预览公告的 RSS 发布日，不声称这是模型全面开放日。
- 摘要：库内官方 RSS 记录了 GPT-5.6 Sol 的预览公告。能力提升属于发布者表述，尚未独立验证。
- 来源身份：`openai`；证据角色：`official`；组织：`openai`；赛道：`general_foundation_models`；人物：无。
- 保留理由/待查：用于区分“预览”与“全面发布”；需核对开放对象与范围，不把 Sol 与后续 GPT-5.6 自动认定为同一型号。

### 2. `event_gpt56_introduction`

- 材料 #139：GPT-5.6: Frontier intelligence that scales with your ambition
- 原始链接：https://openai.com/index/gpt-5-6
- 库存发布时间：Thu, 09 Jul 2026 10:00:00 GMT
- 库存原文摘录：More intelligence from every token, stronger performance per dollar, and more capability on demand for your hardest work.
- 候选标题：OpenAI 介绍 GPT-5.6，发布范围待核实
- 类型：`model_release`（暂定）；状态：`needs_evidence`；人工确认：否
- 事件日期：空，`unknown`；保留文档发布日期，但不自动当作事件发生日期。
- 摘要：标题可识别 GPT-5.6，原文摘录只包含能力宣传。不能仅依据 AI 中文摘要中的“发布”确认正式开放时间或范围。
- 来源身份：`openai`；证据角色：`official`；组织：`openai`；赛道：`general_foundation_models`；人物：无。
- 保留理由/待查：作为证据不足样本；需核对原文的发布行为、时间和可用范围，不能从摘要补出事实。

### 3. `event_gpt56_copilot_adoption`

- 材料 #136：GPT-5.6 is now the preferred model in Microsoft 365 Copilot
- 原始链接：https://openai.com/index/gpt-5-6-preferred-model-microsoft-365-copilot
- 库存发布时间：Thu, 09 Jul 2026 13:00:00 GMT
- 库存原文摘录：Learn how GPT-5.6 powers Microsoft 365 Copilot with stronger AI capabilities across Word, Excel, PowerPoint, Chat, and Cowork for faster, higher-quality work.
- 候选标题：OpenAI 报道 GPT-5.6 成为 Microsoft 365 Copilot 首选模型
- 类型：`adoption`；状态：`candidate`；人工确认：否
- 事件日期：空，`unknown`；公告的发布时间不等于实际采用起始日。
- 摘要：标题将 GPT-5.6 描述为 Microsoft 365 Copilot 的 preferred model；原文摘录描述了所支持的应用。尚不确认默认设置、覆盖所有用户或具体推出日期。
- 来源身份：`openai`；证据角色：`official`（OpenAI 自述，而非 Microsoft 独立确认）；组织：`openai`；赛道：`general_foundation_models`；人物：无。
- 保留理由/待查：将模型介绍与下游采用分开；库存 AI 中文摘要写成“默认模型”，不能替代原文“首选模型”。不修改旧文章 AI 字段，只在事件证据中纠正这种混用。

以上共同研究问题保存在 `events.notes`，具体证据边界保存在关联备注。新增原因：本轮用户授权的最小事件试点，按完整预览保留为未确认内容。

## 实现与验收边界

- 复用 `events`、事件参与者/赛道关系、`documents`、`event_documents`；迁移 `0007` 仅新增事件修改日志，不自动灌入样本。
- 读取与预览不迁移、不写入。保存前预览完整内容；事务中重新验证事件版本、材料快照和预览令牌，原子保存事件、文档、关系和日志。文档第一次从 RSS 原文摘录映射后保留快照，事件编辑不覆写原文。
- 事件表单支持从已有文章创建事件、向已有事件关联多篇材料、修改日期/关系/证据角色/说明、显式人工确认、转待补证据/争议/归档。暂不做自动合并、自由上传或网页正文管线。
- 三篇样本不自动确认。已确认时间线只显示 `status=confirmed` 且 `confirmed_by_user=1` 的记录。日期未知单独置后，不补造年月日。
- 纠错需填写理由，保留前后快照；确认后修改若要保持已确认状态，必须再次勾选确认，否则拒绝保存，需明确改为候选或其他未确认状态。页面预览不等于用户已确认来源。
- 原始链接、RSS 发布时间、摘录与来源角色始终可回溯；AI 翻译和评分不作为原始证据。
- 用临时数据库完成创建→关联→人工确认动作测试→时间线→纠错→归档测试；测试中的模拟确认不代表用户确认真实样本。
- 本轮不建设完整 V4.3 主张/观点系统，不扩名册，不改变三大导航或最终视觉方向，不自动采集，不消耗模型或 Firecrawl 额度。

## 验收记录

2026-09-14：全套 101 项测试通过。本轮全套测试额外拦截对活动数据库的连接，验证测试隔离。用活动库只读副本和三篇真实 RSS 摘录在临时库验证创建、模拟确认、确认时间线与纠错留痕；自动化测试另覆盖真实 HTTP 表单到临时 SQLite 的完整闭环、多材料关联、归档、版本冲突、文档 ID 冲突、原文变更和审计失败回滚。模拟确认仅发生在临时库。

活动库已按用户批准保存本批次：3 个事件（2 candidate、1 needs_evidence，均 origin=ai、confirmed_by_user=0）、3 个 rss_excerpt 文档、3 条创建日志。articles、sources、organizations 保存前后逐行相同；外键检查无错误，完整性检查为 ok。

样本写入前备份：`var/backups/orbitai_before_event_samples_20260914T061544919674Z.db`。

过程异常如实记录：迁移 0007 在 2026-09-13 被旧状态页回归测试经真实材料仓储的 init_db 提前应用，发生在计划备份之前，仅新增空事件日志表和迁移记录。已修复该测试的仓储隔离，未回滚活动库；上面的备份是**迁移后、样本写入前**备份，不能称为迁移前备份。旧仓储读取自动迁移的历史行为尚未整体重构，新事件服务不沿用它。

尚未验证的是实际内容确认与阅读体验，不是要求用户重做上述工程测试。按 2026-09-15 的协作调整，由代理准备具体内容、来源依据、疑点与推荐处理，并整理真实发生的使用记录；用户确认适当事件或保留待补证据，反馈介绍和来源查找是否清楚。技术纠错演练由代理完成，实际复用与耗时记录随自然使用积累，未发生时如实留空。技术路径已验证不代表实际使用收益或全部 V4.2 已完成；等待反馈不阻塞其他已授权且不依赖该反馈的工作。
