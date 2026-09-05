# Goal Workflow

`goal-workflow` 是一个自包含的 Codex skill：它通过逐步访谈把粗略任务整理成可执行、可验证的 Goal mode prompt，并在保存和启动前分别取得确认。调查阶段还会确认是否需要并行 subagent；启用时可选择运行时支持的模型和推理深度。

```text
$goal-workflow 重构这个项目的认证模块
```

它适合目标模糊、存在多种方案，或需要明确范围、风险、验证、发布与停止条件的任务。skill 自带目标质量检查和方案探索流程，不依赖外部 `$define-goal` 或 `$brainstorming` skill，也没有 npm、pip 等包管理器依赖。

## 安装和更新

统一使用仓库根 URL，让 Codex 只注册一个 `goal-workflow` skill：

```text
安装 skill https://github.com/zuchengchen/goal-workflow
```

更新同一个安装，不保留旧目录备份：

```text
更新 skill https://github.com/zuchengchen/goal-workflow
```

这两行是本项目约定的 Codex 请求。不要再使用 `/tree/.../skills/goal-workflow`
这种 nested URL，也不要修改 Codex 自带的
`skill-installer`。当前系统安装器对 GitHub 根 URL 的参数要求和已有目录更新策略
可能不同；本仓库用自己的 `scripts/update-installed-skill.py` 处理这两种请求。

在 shell 中执行项目更新器的最小流程如下。它只替换
`${CODEX_HOME:-$HOME/.codex}/skills/goal-workflow`，不保留备份；`--prune-duplicates`
只会删除已确认是本 skill 的其他可见副本：

```bash
tmp_dir="$(mktemp -d)"
trap 'rm -rf -- "$tmp_dir"' EXIT
git clone --depth 1 https://github.com/zuchengchen/goal-workflow "$tmp_dir/goal-workflow"
python3 "$tmp_dir/goal-workflow/scripts/update-installed-skill.py" \
  --source-dir "$tmp_dir/goal-workflow" --prune-duplicates
```

唯一推荐的用户级目标是 `${CODEX_HOME:-$HOME/.codex}/skills/goal-workflow`；更新完成后
重启 Codex，使会话重新加载唯一副本。完整的固定版本、重复副本和迁移步骤见
[INSTALL.md](INSTALL.md)。

当前 source 版本为 `0.2.0`。手动 clone、项目级复制、验证、卸载、重复副本清理和迁移步骤统一见 [INSTALL.md](INSTALL.md)。

## 工作流摘要

- 根据任务复杂度选择适当的访谈深度，一次只问一个问题。
- 在需要时检查项目上下文、比较 2-3 个方案并确认方向。
- 覆盖目标、范围、约束、兼容性、安全、测试、发布、回滚和停止条件。
- 将每项自动验证视为需要校准的判定器，保留生产命令退出码、使用当前运行证据，并防止文本扫描的假阳性和假阴性。
- 在 investigating 阶段询问是否启用 bounded parallel subagent，并分别询问模型与 reasoning depth；只有运行时暴露对应能力时才会保存和使用这些设置。
- 父 Goal 负责共享文件、合并和最终验证；subagent 只处理有明确边界的独立批次，不能创建重复 Goal 或修改共享状态。
- 起草后先确认是否保存，保存后再确认是否启动 Goal mode。
- 默认将 goal 文件保存到项目根的 `.codex/goals/`；无法确定项目根时使用当前工作目录下的 `.codex/goals/`。

是否提交 `.codex/goals/` 由项目决定：个人 goal 通常应加入 `.gitignore`，团队共享的 goal 可以显式纳入版本控制。

## `Waiting for agents` 的含义

这不是 `goal-workflow` 的工作流状态，而是 Goal 运行时的等待提示。通常表示父 Goal 已派发一个或多个 subagent，正在等待仍处于 queued/running 状态的 child handle；也可能是运行时并发上限、子任务工具调用未返回、失败信号未送达，或恢复旧 Goal 后留下的 stale dispatcher/UI 状态。启用 subagent 后，父 Goal 必须检查当前 handle 属于本次 Goal 和批次，等所有结果返回后再合并，不能用轮询或重复创建 Goal 来掩盖等待。

如果保存的 `Subagent Options` 是 `enabled: false`，本 skill 不会派发 agent。此时仍出现 `Waiting for agents`，应先检查当前 Goal 状态和运行时 agent 状态；没有当前 pending handle 时，应报告运行时不一致，并只使用实际暴露的取消或 `/goal` 生命周期命令。skill 不会假设一个并不存在的 dispatch/join 工具，也不会悄悄换用另一个模型或推理深度。

## 要求

- 支持 Agent Skills 的 Codex。
- 可用的 Goal mode；如果 `/goal` 不可用，可运行 `codex features enable goals` 后重启 Codex。
- 仅在 clone、更新或检出固定版本时需要 Git。

## 仓库布局

```text
goal-workflow/
├── skills/goal-workflow/   # canonical 可安装 skill
├── SKILL.md + agents/      # 与 canonical 同步的旧安装兼容镜像
├── scripts/                # 安装、卸载、烟测和结构验证
├── tests/                  # 行为与结构测试
├── .github/workflows/      # CI 验证
├── docs/history/           # 历史 goal 文档
├── INSTALL.md              # 完整安装与迁移说明
├── CHANGELOG.md
├── VERSION
└── LICENSE
```

仓库内的可安装内容仍由 `skills/goal-workflow/` 维护，根目录 `SKILL.md` 和 `agents/`
是兼容镜像。项目更新器只从仓库根 URL 取得 source，再将 canonical bundle 发布为唯一的
`goal-workflow` 目录，不会同时注册根镜像和 nested canonical 目录。

发布历史见 [CHANGELOG.md](CHANGELOG.md)。
