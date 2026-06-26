# Goal Workflow

`goal-workflow` 是一个 Codex Agent Skill，用来把一句粗略任务转成可执行的 Codex Goal mode 提示词。它会先用轻量的 brainstorming 流程帮助你探索方向、比较方案并确认设计取舍，然后澄清目标、范围、验证方式和停止条件，得到确认后保存 goal 文件，再二次确认是否启动 Goal mode。

典型用法：

```text
$goal-workflow 重构这个项目的认证模块
```

## 它做什么

- 对模糊、设计型或多方案任务，先检查相关上下文，再给出 2-3 个可选方案、取舍和推荐方向。
- 一次只问一个关键澄清问题，避免把 brainstorming 或目标定义流程变成大段表单。
- 在模糊或设计型任务中，先确认设计方向，再起草最终 Goal mode 提示词。
- 自动应用 `$define-goal` 风格的目标澄清标准。
- 生成适合 Goal mode 的 Markdown 提示词。
- 在保存 goal 文件前要求用户确认。
- 保存后再次确认，才启动或交接给 Goal mode。
- 默认把 goal 文件保存到当前工作目录，文件名形如 `<YYYY-MM-DD>-<short-slug>.md`。

## 目录结构

```text
goal-workflow/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── INSTALL.md
└── README.md
```

`SKILL.md` 是技能主体，`agents/openai.yaml` 是 Codex UI 使用的展示元数据。

## 依赖

这个仓库本身没有 npm、pip、Go、Rust 等项目依赖，也没有构建步骤。

运行时需要：

- Codex CLI、Codex IDE extension 或 Codex app，且当前版本支持 Agent Skills。
- Codex Goal mode。若 `/goal` 不在 slash command 列表中，可以运行：

```bash
codex features enable goals
```

推荐但不是强制：

- `$define-goal` skill。`goal-workflow` 会优先使用它的目标定义标准；如果没有安装，也会使用内置的目标质量检查规则继续工作。

不需要额外安装：

- `$brainstorming` skill。`goal-workflow` 已经内置了适合 Codex Goal mode 的 brainstorming 阶段，但不会安装或复制 Claude Code / Superpowers 的独立 skill。

注意：当前 Codex skill 元数据不支持声明“安装本 skill 时自动安装另一个 skill”的传递依赖；`agents/openai.yaml` 目前主要支持 MCP 工具依赖。因此如果你想同时安装 `$define-goal`，请在安装提示词里明确要求 Codex 一并安装或确认。

如果只是安装这个 skill，不需要运行 `npm install`、`pip install`、`poetry install` 或类似命令。

## 快速安装

最简单的方式是在 Codex 中直接输入安装请求：

```text
安装 skill https://github.com/zuchengchen/goal-workflow，并同时安装 $define-goal skill
```

如果只想安装本 skill，也可以输入：

```text
安装 skill https://github.com/zuchengchen/goal-workflow
```

建议使用不带 `.git` 的 GitHub URL。Codex 通常能理解 `https://github.com/zuchengchen/goal-workflow.git`，但 `$skill-installer` 的脚本接口按 GitHub 页面 URL 解析，不带 `.git` 更稳。

通过 Codex 安装器安装时，默认会安装到 `$CODEX_HOME/skills`，通常是 `~/.codex/skills`。

安装后启动一个新的 Codex 会话，输入 `$goal-workflow` 或在 CLI/IDE 中输入 `$` 查看技能是否出现。如果没有出现，重启 Codex。

更完整的安装、更新、卸载和排错步骤见 [INSTALL.md](INSTALL.md)。

## 手动安装

如果不想通过 Codex 安装器，也可以手动安装到当前用户的 skills 目录：

```bash
mkdir -p "$HOME/.agents/skills"
git clone git@github.com:zuchengchen/goal-workflow.git "$HOME/.agents/skills/goal-workflow"
```

如果没有配置 GitHub SSH，也可以使用 HTTPS：

```bash
mkdir -p "$HOME/.agents/skills"
git clone https://github.com/zuchengchen/goal-workflow.git "$HOME/.agents/skills/goal-workflow"
```

## 仓库级安装

如果希望某个项目团队共享这个 skill，可以把它放到目标项目的 `.agents/skills/goal-workflow`：

```bash
mkdir -p .agents/skills
git clone git@github.com:zuchengchen/goal-workflow.git .agents/skills/goal-workflow
```

如果目标项目本身也是 Git 仓库，更推荐使用 submodule 或复制文件，避免意外提交嵌套 `.git` 目录：

```bash
git submodule add git@github.com:zuchengchen/goal-workflow.git .agents/skills/goal-workflow
```

Codex 会从当前工作目录向上扫描 `.agents/skills`，因此仓库级安装适合只在特定项目中启用这个工作流。

## 使用示例

```text
$goal-workflow 给这个仓库补一套最小但可靠的测试
```

技能会引导你确认：

- 这个任务是否需要先 brainstorming，或是否可以轻量跳过。
- 当前项目上下文里有哪些相关约束和已有模式。
- 可选方案、主要取舍和推荐方向。
- 最终要达成的具体结果。
- 涉及哪些仓库、文件、模块或用户流程。
- 哪些内容在范围内，哪些不做。
- 用什么命令、测试、人工检查或验收标准证明完成。
- 遇到哪些情况时 Codex 应该停止询问，而不是自行猜测。

如果问题包含多个预设选项，技能会用 `1.`、`2.`、`3.` 这样的数字编号列出选项，你可以只回复数字来选择。对于“是/否”问题，技能会提示用 `y` 或 `Y` 表示是，用 `n` 或 `N` 表示否。

对于模糊或设计型任务，它会先询问你是否认可推荐方向；当 goal prompt 草稿完成后，它会再询问是否保存。保存后，它会再次询问是否启动 Goal mode。

## 更新

如果通过 Git 安装：

```bash
cd "$HOME/.agents/skills/goal-workflow"
git pull --ff-only
```

更新后如果当前会话没有读取到变化，重启 Codex。

## 卸载

用户级安装：

```bash
rm -rf "$HOME/.agents/skills/goal-workflow"
```

仓库级安装：

```bash
rm -rf .agents/skills/goal-workflow
```

如果使用了 Git submodule，请按 submodule 的常规方式移除，避免留下 `.gitmodules` 残留配置。
