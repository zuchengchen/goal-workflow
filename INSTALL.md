# 安装与依赖

本文档说明如何安装 `goal-workflow` skill，以及它需要哪些依赖。

## 前置条件

### 1. 安装 Codex

如果本机还没有 `codex` 命令，可以先安装 Codex CLI：

```bash
curl -fsSL https://chatgpt.com/codex/install.sh | sh
```

安装后登录：

```bash
codex login
```

确认 CLI 可用：

```bash
codex --version
codex doctor
```

### 2. 安装 Git

如果你准备通过 `git clone` 安装，需要本机已有 Git：

```bash
git --version
```

如果没有 Git，请先用系统包管理器安装，例如 Ubuntu/Debian：

```bash
sudo apt update
sudo apt install git
```

## 最简单安装方式

推荐直接在 Codex 中输入自然语言安装请求：

```text
安装 skill https://github.com/zuchengchen/goal-workflow，并同时安装 $define-goal skill
```

这会让 Codex 使用 `$skill-installer` 类安装流程来安装 GitHub skill。当前仓库的 skill 位于仓库根目录，并且远程分支是 `master`，所以提示词里明确写出“仓库根目录，分支 master”最稳。

通过 Codex 安装器安装时，默认目标目录是 `$CODEX_HOME/skills`，通常是 `~/.codex/skills`。

如果只安装 `goal-workflow`，可以输入：

```text
安装 skill https://github.com/zuchengchen/goal-workflow
```

建议使用不带 `.git` 的 URL。`https://github.com/zuchengchen/goal-workflow.git` 对人类来说清楚，但安装脚本的 URL 解析更适合不带 `.git` 的 GitHub 页面地址。

## 关于 `$define-goal` 自动安装

`$define-goal` 是推荐依赖，不是硬依赖。`goal-workflow` 会优先使用 `$define-goal` 的目标定义标准；如果它不存在，仍会使用内置的目标质量规则继续工作。

`goal-workflow` 还内置了适合 Codex Goal mode 的 brainstorming 阶段。它会在模糊、设计型或多方案任务中先比较方向，再进入目标定义；这不需要额外安装 Claude Code / Superpowers 的 `$brainstorming` skill。

当前 Codex skill 元数据不支持声明另一个 skill 作为传递安装依赖。换句话说，仅安装：

```text
安装 skill https://github.com/zuchengchen/goal-workflow
```

不会由 `goal-workflow` 仓库自动触发 `$define-goal` 安装。

如果你希望一次完成，请把要求写在同一句安装提示词里：

```text
安装 skill https://github.com/zuchengchen/goal-workflow，并同时安装 $define-goal skill
```

如果 Codex 找不到可安装的 `$define-goal` 来源，它会说明原因；此时 `goal-workflow` 仍然可用。

## 安装方式一：用户级手动安装

用户级安装会让当前用户在任意仓库里都能使用 `$goal-workflow`。

使用 SSH：

```bash
mkdir -p "$HOME/.agents/skills"
git clone git@github.com:zuchengchen/goal-workflow.git "$HOME/.agents/skills/goal-workflow"
```

使用 HTTPS：

```bash
mkdir -p "$HOME/.agents/skills"
git clone https://github.com/zuchengchen/goal-workflow.git "$HOME/.agents/skills/goal-workflow"
```

安装后目录应类似：

```text
$HOME/.agents/skills/goal-workflow/
├── SKILL.md
└── agents/
    └── openai.yaml
```

## 安装方式二：仓库级安装

仓库级安装会让这个 skill 只在某个项目中可用，适合团队共享项目专用工作流。

进入目标项目根目录后执行：

```bash
mkdir -p .agents/skills
git clone git@github.com:zuchengchen/goal-workflow.git .agents/skills/goal-workflow
```

如果目标项目本身是 Git 仓库，并且你希望保留 `goal-workflow` 的上游更新能力，建议使用 submodule：

```bash
git submodule add git@github.com:zuchengchen/goal-workflow.git .agents/skills/goal-workflow
git commit -m "Add goal workflow skill"
```

如果不想使用 submodule，也可以从本仓库复制文件到目标项目：

```bash
cd /path/to/goal-workflow
mkdir -p .agents/skills/goal-workflow
cp -R SKILL.md agents /path/to/target-project/.agents/skills/goal-workflow/
```

复制方式适合一次性引入，但后续需要手动同步更新。

## 安装方式三：管理员级安装

如果希望机器上所有用户都能使用，可以安装到系统级目录：

```bash
sudo mkdir -p /etc/codex/skills
sudo git clone git@github.com:zuchengchen/goal-workflow.git /etc/codex/skills/goal-workflow
```

系统级安装需要管理员权限。团队机器或容器镜像中可以使用这种方式。

## 安装依赖

这个 skill 是纯说明型 Codex skill，没有语言运行时依赖和包管理器依赖。

不需要执行：

```bash
npm install
pip install -r requirements.txt
poetry install
pnpm install
```

实际依赖只有：

| 依赖 | 是否必需 | 说明 |
| --- | --- | --- |
| Codex | 必需 | 用于加载和执行 Agent Skills。 |
| Git | 可选 | 仅在使用 `git clone` 或 `git pull` 安装/更新时需要。 |
| Goal mode | 必需 | 该 skill 的最终输出面向 `/goal`。 |
| `$define-goal` skill | 推荐 | 用于复用更完整的目标定义标准；没有时会使用内置降级规则。 |
| `$brainstorming` skill | 不需要 | 已内置 brainstorming 阶段，不依赖独立 skill。 |

如果 `/goal` 不可用，请启用 goals feature：

```bash
codex features enable goals
```

也可以手动编辑 Codex 配置，加入：

```toml
[features]
goals = true
```

保存后重启 Codex。

## 验证安装

### 1. 检查文件存在

Codex 安装器默认安装：

```bash
test -f "${CODEX_HOME:-$HOME/.codex}/skills/goal-workflow/SKILL.md"
```

用户级安装：

```bash
test -f "$HOME/.agents/skills/goal-workflow/SKILL.md"
```

仓库级安装：

```bash
test -f ".agents/skills/goal-workflow/SKILL.md"
```

### 2. 启动新会话

```bash
codex
```

在输入框中输入 `$`，查看是否能看到 `goal-workflow`。也可以直接输入：

```text
$goal-workflow 帮我把这个任务整理成可执行 Goal
```

### 3. 检查 Goal mode

在 Codex 中输入：

```text
/goal
```

如果 slash command 不存在，运行：

```bash
codex features enable goals
```

然后重启 Codex。

## 更新

用户级 Git 安装：

```bash
cd "$HOME/.agents/skills/goal-workflow"
git pull --ff-only
```

仓库级 submodule 安装：

```bash
git submodule update --remote .agents/skills/goal-workflow
git add .agents/skills/goal-workflow
git commit -m "Update goal workflow skill"
```

复制安装：

```bash
cp -R SKILL.md agents /path/to/target/.agents/skills/goal-workflow/
```

更新后建议重启 Codex，确保当前会话读取到最新技能内容。

## 卸载

用户级安装：

```bash
rm -rf "$HOME/.agents/skills/goal-workflow"
```

仓库级安装：

```bash
rm -rf .agents/skills/goal-workflow
```

管理员级安装：

```bash
sudo rm -rf /etc/codex/skills/goal-workflow
```

如果使用 Git submodule，还需要清理 `.gitmodules` 和 Git 索引中的 submodule 记录。

## 常见问题

### 输入 `$goal-workflow` 没反应

先确认 `SKILL.md` 在 Codex 会扫描的 skills 目录中，然后重启 Codex。仓库级 skill 需要你从目标仓库或其子目录启动 Codex。

### `$goal-workflow` 出现了，但 `/goal` 不存在

启用 goals feature：

```bash
codex features enable goals
```

然后重启 Codex。

### 没有 `$define-goal` 可以用吗

可以。`goal-workflow` 会优先使用 `$define-goal`，但没有它时仍会按照 `SKILL.md` 中的目标质量标准继续访谈、起草和保存 goal prompt。

### 需要安装 npm 或 Python 依赖吗

不需要。这个仓库没有 `package.json`、`requirements.txt` 或其他依赖清单。

### 更新后技能描述没有变化

重启 Codex。Codex 通常能检测 skill 变化，但已打开的会话可能仍保留旧上下文。
