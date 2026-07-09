# 安装、更新与迁移

本文是 `goal-workflow` 唯一的详细安装说明。README 只提供快速入口；安装路径、版本固定、迁移和排错以本文为准。

## 安装标识

| 项目 | 值 |
| --- | --- |
| 仓库 | `https://github.com/zuchengchen/goal-workflow` |
| canonical URL | `https://github.com/zuchengchen/goal-workflow/tree/master/skills/goal-workflow` |
| moving ref | `master` |
| 仓库内精确 path | `skills/goal-workflow` |
| skill 名称 | `goal-workflow` |
| 安装器默认目标 | `${CODEX_HOME:-$HOME/.codex}/skills/goal-workflow` |

canonical URL 同时编码了精确 ref 和 path。不要只把仓库根 URL 交给安装器，也不要依赖安装器默认的 `main` 分支；本仓库的 moving ref 是 `master`，canonical 安装路径不再是仓库根。

为保证可复现，正式环境和团队配置应优先把 URL 中的 `master` 替换为已发布 tag（当前 source 版本 `0.2.0` 发布后对应 `v0.2.0`）或完整 commit SHA：

```text
https://github.com/zuchengchen/goal-workflow/tree/v0.2.0/skills/goal-workflow
https://github.com/zuchengchen/goal-workflow/tree/<full-commit-sha>/skills/goal-workflow
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

发布 tag 后，推荐固定安装当前版本：

```text
使用 $skill-installer 安装这个 skill：
https://github.com/zuchengchen/goal-workflow/tree/v0.2.0/skills/goal-workflow
```

tag 尚未发布时，把 `v0.2.0` 换成实际存在的完整 commit SHA。只有确实希望跟随最新提交时，才改用 canonical moving-source URL：

```text
https://github.com/zuchengchen/goal-workflow/tree/master/skills/goal-workflow
```

安装器从 URL 得到：

- 仓库：`zuchengchen/goal-workflow`
- ref：版本 tag、完整 commit SHA 或 moving ref `master`
- path：`skills/goal-workflow`
- 目标：`${CODEX_HOME:-$HOME/.codex}/skills/goal-workflow`

安装器不会覆盖已有同名目录。如果目标已经存在，先按“同名冲突”一节检查或备份，再执行安装。

安装完成后启动新的 Codex 会话。已打开的会话可能仍保留旧的 skill 上下文。

## 方法二：手动 clone 后复制到用户目录

下面的命令默认固定到当前 release tag。tag 尚未发布时，把 `ref` 改为实际存在的完整 commit SHA；只有确实希望跟随最新提交时才设为 `master`。

```bash
install_root="${CODEX_HOME:-$HOME/.codex}/skills"
dest="$install_root/goal-workflow"
ref="v0.2.0"
tmp_dir="$(mktemp -d)"
source_dir="$tmp_dir/goal-workflow"

cleanup() {
  rm -rf -- "$tmp_dir"
}
trap cleanup EXIT

test ! -e "$dest" || {
  echo "目标已存在：$dest" >&2
  echo "请先检查、备份或按更新步骤处理。" >&2
  exit 1
}

git clone https://github.com/zuchengchen/goal-workflow.git "$source_dir"
git -C "$source_dir" checkout --detach "$ref"
"$source_dir/scripts/install-local.sh" --dest "$dest"
```

固定到 commit 时必须使用完整 SHA：

```bash
ref="0123456789abcdef0123456789abcdef01234567"
```

在主命令块执行前，把示例 SHA 替换为准备安装的真实 40 位 commit SHA。若要保留一个正常 clone 作为后续更新源，请使用固定路径代替临时目录并省略清理命令。安装目录本身只包含 canonical skill 文件，不应包含仓库根 README、历史 goal 或 `.git`。

## 方法三：复制到项目仓库

项目级安装适合只在某个仓库中启用或由团队共同维护。先 clone 并检出所需版本：

```bash
git clone https://github.com/zuchengchen/goal-workflow.git /path/to/goal-workflow-source
git -C /path/to/goal-workflow-source checkout --detach v0.2.0
```

然后用仓库自带的安全安装脚本把 canonical skill 复制到目标项目。脚本会验证 source 和目标路径、默认拒绝覆盖，并通过临时目录发布完整安装：

```bash
target_project="/path/to/target-project"
dest="$target_project/.agents/skills/goal-workflow"

/path/to/goal-workflow-source/scripts/install-local.sh --dest "$dest"
```

不要把整个 `goal-workflow` 仓库直接 clone 或作为 submodule 放到 `.agents/skills/goal-workflow` 作为新安装方案。0.2.x 的仓库根保留了与 canonical 内容一致的兼容镜像，旧安装仍能工作，但会携带仓库文档、测试和历史文件；新安装应只复制 `skills/goal-workflow/`，让安装目录仅包含运行所需内容。

## 从本地仓库直接复制

如果当前工作目录就是本仓库根，可安装到用户目录：

```bash
scripts/install-local.sh
```

复制到另一个项目：

```bash
scripts/install-local.sh --dest "/path/to/target-project/.agents/skills/goal-workflow"
```

脚本只接受名为 `goal-workflow` 且直接位于非根 `skills` 目录中的目标，避免写入错误位置。目标已存在时默认失败；需要更新时使用后文的 `--replace` 流程。

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

安装器发现 `${CODEX_HOME:-$HOME/.codex}/skills/goal-workflow` 已存在时会停止。不要直接覆盖或把两个版本合并到同一目录，否则可能留下已经删除的旧文件。

先确认现有目录来源：

```bash
dest="${CODEX_HOME:-$HOME/.codex}/skills/goal-workflow"
find "$dest" -maxdepth 2 -type f -print
git -C "$dest" remote -v 2>/dev/null || true
```

需要保留时先重命名备份：

```bash
dest="${CODEX_HOME:-$HOME/.codex}/skills/goal-workflow"
backup="${dest}.backup.$(date +%Y%m%d%H%M%S)"
mv "$dest" "$backup"
```

然后重新安装并验证。确认新版本工作正常后，再由你决定是否删除备份。

项目级 `.agents/skills/goal-workflow` 采用同样策略。若用户级和项目级同时存在同名 skill，优先保留单一、明确的来源，避免不同版本随启动目录变化。

## 更新

### 安装器或复制安装

保留 source checkout 时，优先使用 transactional replace。脚本会验证现有 skill 身份、把新版本安装到 staging、保留旧目录备份，并在发布失败时尝试恢复：

```bash
dest="${CODEX_HOME:-$HOME/.codex}/skills/goal-workflow"
/path/to/goal-workflow-source/scripts/install-local.sh --dest "$dest" --replace
```

脚本会打印保留的备份路径。验证通过后重启 Codex，再由你决定是否删除备份。

如果只有 Codex 安装器而没有 source checkout，则先按“同名冲突”一节重命名旧目录，再按“方法一”安装新的固定版本；不要在旧目录上增量覆盖。

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

0.1.x 允许把整个仓库根直接安装成 skill。0.2.0 起，canonical skill 位于 `skills/goal-workflow/`。0.2.x 暂时保留受自动校验的根目录兼容镜像，因此旧 Git 安装执行 `git pull` 后仍可工作；但它不是长期安装接口，仍应迁移到只包含 canonical skill 的新目录。

常见旧目录包括：

```text
${CODEX_HOME:-$HOME/.codex}/skills/goal-workflow
$HOME/.agents/skills/goal-workflow
<project>/.agents/skills/goal-workflow
```

迁移用户级旧安装：

```bash
new_dest="${CODEX_HOME:-$HOME/.codex}/skills/goal-workflow"
timestamp="$(date +%Y%m%d%H%M%S)"

if [ -e "$new_dest" ]; then
  mv "$new_dest" "${new_dest}.pre-0.2.0.$timestamp"
fi

legacy_dest="$HOME/.agents/skills/goal-workflow"
if [ "$legacy_dest" != "$new_dest" ] && [ -e "$legacy_dest" ]; then
  mv "$legacy_dest" "${legacy_dest}.pre-0.2.0.$timestamp"
fi
```

随后使用 canonical URL 安装 0.2.0，并按“验证安装”检查。确认新版本工作正常后，再删除旧目录备份。旧 Git clone 也可以先更新并作为 source 使用，但最终安装目录应只复制 `skills/goal-workflow/.`。项目级旧安装同样先重命名备份，再复制到全新的 `.agents/skills/goal-workflow/`。

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

确认使用的是完整 canonical URL，而不是仓库根 URL：

```text
https://github.com/zuchengchen/goal-workflow/tree/master/skills/goal-workflow
```

其中 ref 是 `master`，path 是 `skills/goal-workflow`。

### `$goal-workflow` 没有出现

确认安装目录顶层存在 `SKILL.md` 和 `agents/openai.yaml`，然后启动新 Codex 会话。项目级安装要求从目标项目或其子目录启动 Codex。

### `$goal-workflow` 出现，但 `/goal` 不可用

```bash
codex features enable goals
```

重启 Codex 后再检查。

### 更新后仍看到旧行为

检查是否同时存在 `${CODEX_HOME:-$HOME/.codex}/skills/goal-workflow`、`$HOME/.agents/skills/goal-workflow` 和项目级 `.agents/skills/goal-workflow`。移除或备份重复来源，并启动新会话。

### 是否需要安装 `$define-goal`

不需要。0.2.0 起 `goal-workflow` 自包含目标质量标准和完整工作流，不读取或调用外部 `$define-goal`。
