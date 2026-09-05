# 安装、更新与迁移

本文是 `goal-workflow` 唯一的详细安装说明。README 只提供快速入口；安装路径、版本固定、迁移和排错以本文为准。

## 安装标识

| 项目 | 值 |
| --- | --- |
| 仓库 | `https://github.com/zuchengchen/goal-workflow` |
| 安装/更新 URL | `https://github.com/zuchengchen/goal-workflow` |
| moving ref | `master` |
| 仓库内精确 path | `skills/goal-workflow` |
| skill 名称 | `goal-workflow` |
| 安装器默认目标 | `${CODEX_HOME:-$HOME/.codex}/skills/goal-workflow` |

Codex 安装器统一接收仓库根 URL，并从根目录兼容镜像发布唯一的 `goal-workflow` skill。仓库内部的实际维护源仍是 `skills/goal-workflow/`；不要再把 nested path URL 交给安装器，也不要依赖安装器默认的 `main` 分支。本仓库的 moving ref 是 `master`。

为保证可复现，正式环境和团队配置可以把仓库根 URL 替换为已发布 tag 或完整 commit SHA：

```text
https://github.com/zuchengchen/goal-workflow/tree/v0.2.0
https://github.com/zuchengchen/goal-workflow/tree/<full-commit-sha>
```

只有确实希望自动跟随最新提交时才使用 `master`。版本 tag 必须已经发布；发布前请固定到实际存在的完整 commit SHA。

## 前置条件

需要支持 Agent Skills 的 Codex。skill 本身是自包含的，不依赖 `$define-goal`、`$brainstorming` 或任何 npm、pip、Go、Rust 包。

如果 `/goal` 不可用，启用 Goal mode 后重启 Codex：

```bash
codex features enable goals
```

只有手动 clone、检出固定版本或从 Git 更新源仓库时才需要 Git：

```bash
git --version
```

## 方法一：使用 Codex 安装器

安装和更新都使用同一个仓库根 URL：

```text
使用 $skill-installer 安装这个 skill：
安装 skill https://github.com/zuchengchen/goal-workflow
更新 skill https://github.com/zuchengchen/goal-workflow
```

把这两条命令交给 `$skill-installer` 在 Codex 中执行。若要固定版本，将根 URL 中的 ref 替换为已存在的 tag 或完整 commit SHA；不要改成 nested `skills/goal-workflow` URL：

```text
https://github.com/zuchengchen/goal-workflow/tree/v0.2.0
```

安装器从 URL 得到：

- 仓库：`zuchengchen/goal-workflow`
- ref：版本 tag、完整 commit SHA 或 moving ref `master`
- 发布入口：仓库根目录的兼容镜像
- 目标：`${CODEX_HOME:-$HOME/.codex}/skills/goal-workflow`

安装命令只创建目标目录；更新命令验证目标身份后直接替换同一个目录，不保留备份。不要同时把相同 skill 安装到 `$HOME/.agents/skills/goal-workflow` 或项目级 `.agents/skills/goal-workflow`，否则 Codex 可能看到多个来源。

仓库根 URL 是唯一公开安装入口；固定版本也只改变根 URL 的 ref，不改变 path。

安装完成后启动新的 Codex 会话。已打开的会话可能仍保留旧的 skill 上下文。

## 方法二：手动 clone 后复制到用户目录

下面的命令从仓库根 clone，再从维护源 `skills/goal-workflow/` 发布到唯一用户级目标。更新时复用同一个目标，不保留备份。

```bash
install_root="${CODEX_HOME:-$HOME/.codex}/skills"
dest="$install_root/goal-workflow"
tmp_dir="$(mktemp -d)"
source_dir="$tmp_dir/goal-workflow"

cleanup() {
  rm -rf -- "$tmp_dir"
}
trap cleanup EXIT

git clone https://github.com/zuchengchen/goal-workflow.git "$source_dir"
git -C "$source_dir" checkout --detach master
"$source_dir/scripts/install-local.sh" --dest "$dest" --replace
```

若要固定版本，把 `git checkout --detach master` 替换为已存在的 tag 或完整 commit SHA。若要保留一个正常 clone 作为后续更新源，请使用固定路径代替临时目录并省略清理命令。安装目录本身只包含 canonical skill 文件，不应包含仓库根 README、历史 goal 或 `.git`。

## 方法三：复制到项目仓库

项目级安装会引入第二个 skill 来源，不属于本项目的推荐路径。若确实需要项目级安装，必须先卸载用户级副本，并始终只保留一个目标。先 clone 并检出所需版本：

```bash
git clone https://github.com/zuchengchen/goal-workflow.git /path/to/goal-workflow-source
git -C /path/to/goal-workflow-source checkout --detach v0.2.0
```

然后用仓库自带的安装脚本把 canonical skill 复制到目标项目。脚本会验证 source 和目标路径，并在更新时直接替换，不保留备份：

```bash
target_project="/path/to/target-project"
dest="$target_project/.agents/skills/goal-workflow"

/path/to/goal-workflow-source/scripts/install-local.sh --dest "$dest"
```

不要把整个 `goal-workflow` 仓库作为长期 `.agents/skills/goal-workflow` 安装，也不要与用户级目标并存。仓库根兼容镜像用于让根 URL 可被安装器识别；本地安装脚本仍只发布 `skills/goal-workflow/` 的运行文件。

## 从本地仓库直接复制

如果当前工作目录就是本仓库根，可安装到用户目录：

```bash
scripts/install-local.sh
```

复制到另一个项目：

```bash
scripts/install-local.sh --dest "/path/to/target-project/.agents/skills/goal-workflow"
```

脚本只接受名为 `goal-workflow` 且直接位于非根 `skills` 目录中的目标，避免写入错误位置。目标已存在时使用 `--replace` 直接更新，不创建持久备份。

## 验证安装

用户级安装：

```bash
dest="${CODEX_HOME:-$HOME/.codex}/skills/goal-workflow"
test -f "$dest/SKILL.md"
test -f "$dest/agents/openai.yaml"
```

项目级安装（从目标项目根执行）：

```bash
test -f .agents/skills/goal-workflow/SKILL.md
test -f .agents/skills/goal-workflow/agents/openai.yaml
```

随后启动一个新的 Codex 会话，输入 `$` 确认列表中存在 `goal-workflow`，或直接运行：

```text
$goal-workflow 把这个任务整理成可执行 Goal
```

再用 `/goal` 检查 Goal mode。仓库中的 `tests/` 和 CI 会验证 canonical skill 的结构、行为不变量和场景契约 schema；模型级前向测试仍需由人工或 agent harness 执行。开发测试不需要复制到安装目录。

## 同名冲突

安装器只管理 `${CODEX_HOME:-$HOME/.codex}/skills/goal-workflow` 这一份用户级副本。更新时验证目标身份并直接替换，不创建或保留备份目录。

先确认现有目录来源：

```bash
dest="${CODEX_HOME:-$HOME/.codex}/skills/goal-workflow"
find "$dest" -maxdepth 2 -type f -print
git -C "$dest" remote -v 2>/dev/null || true
```

发现旧副本时不要重命名成备份；确认它是本 skill 后直接删除，再执行唯一的安装命令：

```bash
dest="${CODEX_HOME:-$HOME/.codex}/skills/goal-workflow"
rm -rf -- "$dest"
```

然后重新安装并验证。完成后只保留 `${CODEX_HOME:-$HOME/.codex}/skills/goal-workflow`。

项目级 `.agents/skills/goal-workflow` 和 `$HOME/.agents/skills/goal-workflow` 都是重复来源。不要与用户级副本并存；若存在，确认用途后删除其中的 skill 副本。

## 更新

### 安装器或复制安装

保留 source checkout 时，使用直接替换。脚本会验证现有 skill 身份、先校验 staging，再替换唯一目标目录，不保留旧目录备份：

```bash
dest="${CODEX_HOME:-$HOME/.codex}/skills/goal-workflow"
/path/to/goal-workflow-source/scripts/install-local.sh --dest "$dest" --replace
```

脚本不会创建或打印备份路径。验证通过后重启 Codex，使会话只加载更新后的唯一副本。

如果只有 Codex 安装器而没有 source checkout，直接再次执行“方法一”的更新命令；若安装器拒绝已有目标，先删除已确认的唯一用户级目录，再执行更新，不要创建备份。

项目级安装同理，只需把 `dest` 改为：

```bash
dest="/path/to/target-project/.agents/skills/goal-workflow"
```

### 更新 source clone

如果保留了独立的 source clone：

```bash
git -C /path/to/goal-workflow-source fetch --tags origin
git -C /path/to/goal-workflow-source checkout --detach v0.2.0
```

然后按复制步骤更新安装目录。跟随 moving ref 时可以改为：

```bash
git -C /path/to/goal-workflow-source checkout master
git -C /path/to/goal-workflow-source pull --ff-only origin master
```

## 从 0.1.x 仓库根安装迁移

0.1.x 允许把整个仓库根直接安装成 skill。现在仓库根 URL 仍是唯一公开安装入口，内部维护源位于 `skills/goal-workflow/`。迁移时只保留一个用户级安装目录，不保留旧目录备份。

常见旧目录包括：

```text
${CODEX_HOME:-$HOME/.codex}/skills/goal-workflow
$HOME/.agents/skills/goal-workflow
<project>/.agents/skills/goal-workflow
```

迁移用户级旧安装：

```bash
new_dest="${CODEX_HOME:-$HOME/.codex}/skills/goal-workflow"
legacy_dest="$HOME/.agents/skills/goal-workflow"

if [ -e "$legacy_dest" ] && [ "$legacy_dest" != "$new_dest" ]; then
  rm -rf -- "$legacy_dest"
fi
```

随后使用仓库根 URL 更新，并按“验证安装”检查。旧 Git clone 不作为 Codex skill 来源；项目级旧安装也应直接删除，确保最后只存在用户级目标目录。

### Goal 文件位置迁移

0.2.0 为避免污染仓库根目录，把新 goal 文件的默认位置改为项目根 `.codex/goals/`；无法确定项目根时使用当前工作目录下的 `.codex/goals/`。旧 goal 文件不会自动移动。

需要整理已有 goal 时，可在确认文件用途后手动移动：

```bash
mkdir -p .codex/goals
git mv path/to/existing-goal-file.md .codex/goals/
```

未被 Git 跟踪的文件使用 `mv`。是否纳入版本控制由项目决定：

- 个人工作用 goal：通常在 `.gitignore` 中加入 `.codex/goals/`。
- 团队共享 goal：不要忽略该目录，审阅后显式提交所需文件。
- `docs/history/` 保存本仓库的历史 goal 文档，不属于运行时安装内容。

## 卸载

有 source checkout 时，先 dry-run，再使用经过路径和 skill 身份校验的卸载脚本：

```bash
/path/to/goal-workflow-source/scripts/uninstall-local.sh --dry-run
/path/to/goal-workflow-source/scripts/uninstall-local.sh
```

项目级安装传入明确目标：

```bash
dest="/path/to/target-project/.agents/skills/goal-workflow"
/path/to/goal-workflow-source/scripts/uninstall-local.sh --dest "$dest" --dry-run
/path/to/goal-workflow-source/scripts/uninstall-local.sh --dest "$dest"
```

没有 source checkout 时，用户级手工回退为：

```bash
dest="${CODEX_HOME:-$HOME/.codex}/skills/goal-workflow"
test "$dest" = "${CODEX_HOME:-$HOME/.codex}/skills/goal-workflow"
test -f "$dest/SKILL.md"
grep -q '^name: goal-workflow$' "$dest/SKILL.md"
rm -rf -- "$dest"
```

旧的用户级兼容目录（仅在你确认其中是本 skill 后执行）：

```bash
dest="$HOME/.agents/skills/goal-workflow"
test -f "$dest/SKILL.md"
grep -q '^name: goal-workflow$' "$dest/SKILL.md"
rm -rf -- "$dest"
```

项目级安装（从目标项目根执行）：

```bash
dest=".agents/skills/goal-workflow"
test -f "$dest/SKILL.md"
grep -q '^name: goal-workflow$' "$dest/SKILL.md"
rm -rf -- "$dest"
```

卸载或更新后重启 Codex。本文不假定或宣称任何系统级 skills 目录；管理员部署应以所用 Codex 版本和组织配置的明确文档为准。

## 排错

### 安装器寻找 `main` 或找不到 `SKILL.md`

确认使用的是仓库根 URL，而不是 nested path URL：

```text
https://github.com/zuchengchen/goal-workflow
```

固定版本时只把仓库根 URL 的 ref 改成 tag 或完整 commit SHA。

### `$goal-workflow` 没有出现

确认安装目录顶层存在 `SKILL.md` 和 `agents/openai.yaml`，然后启动新 Codex 会话。项目级安装要求从目标项目或其子目录启动 Codex。

### `$goal-workflow` 出现，但 `/goal` 不可用

```bash
codex features enable goals
```

重启 Codex 后再检查。

### 更新后仍看到旧行为

检查是否同时存在 `${CODEX_HOME:-$HOME/.codex}/skills/goal-workflow`、`$HOME/.agents/skills/goal-workflow` 和项目级 `.agents/skills/goal-workflow`。只保留 `${CODEX_HOME:-$HOME/.codex}/skills/goal-workflow`，删除其他已确认的 `goal-workflow` 副本，然后重启新会话；不要重命名成备份。

### Goal 启动后显示 `Waiting for agents`

这是运行时等待 child agent 的状态，不是本 skill 的状态机状态。若 goal 的 `Subagent Options` 为 `enabled: true`，先检查当前 Goal 的 pending handles、它们是否属于当前批次，以及运行时是否达到并发上限；只有所有 child 返回后父 Goal 才能合并和验证。长时间不变通常还可能是子任务工具调用未返回、失败信号未送达，或恢复 Goal 后的 stale dispatcher/UI 状态。

若 `enabled: false` 却仍显示该状态，检查是否存在旧的 active Goal 或运行时残留 agent；没有当前 pending handle 时不要重复创建 Goal，改用当前工具实际支持的取消操作或 `/goal` lifecycle 命令，并报告运行时不一致。模型和 reasoning depth 只会使用 investigating 阶段确认且运行时 schema 接受的值。

### 是否需要安装 `$define-goal`

不需要。0.2.0 起 `goal-workflow` 自包含目标质量标准和完整工作流，不读取或调用外部 `$define-goal`。
