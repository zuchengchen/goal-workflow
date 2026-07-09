# Goal Workflow

`goal-workflow` 是一个自包含的 Codex skill：它通过逐步访谈把粗略任务整理成可执行、可验证的 Goal mode prompt，并在保存和启动前分别取得确认。

```text
$goal-workflow 重构这个项目的认证模块
```

它适合目标模糊、存在多种方案，或需要明确范围、风险、验证、发布与停止条件的任务。skill 自带目标质量检查和方案探索流程，不依赖外部 `$define-goal` 或 `$brainstorming` skill，也没有 npm、pip 等包管理器依赖。

## 安装

canonical moving-source 地址（分支随 `master` 更新）：

```text
https://github.com/zuchengchen/goal-workflow/tree/master/skills/goal-workflow
```

发布 tag 后，推荐在 Codex 中固定安装当前版本：

```text
使用 $skill-installer 安装：
https://github.com/zuchengchen/goal-workflow/tree/v0.2.0/skills/goal-workflow
```

当前 source 版本为 `0.2.0`。tag 尚未发布时应把 URL 中的 ref 换成实际存在的完整 commit SHA；只有确实希望跟随最新提交时才使用上面的 `master` URL。安装器写入 `${CODEX_HOME:-$HOME/.codex}/skills/goal-workflow`，遇到同名目录会停止，不会覆盖。

手动安装、项目级复制、版本固定、验证、更新、卸载、同名冲突和 0.2.0 迁移步骤统一见 [INSTALL.md](INSTALL.md)。

## 工作流摘要

- 根据任务复杂度选择适当的访谈深度，一次只问一个问题。
- 在需要时检查项目上下文、比较 2-3 个方案并确认方向。
- 覆盖目标、范围、约束、兼容性、安全、测试、发布、回滚和停止条件。
- 起草后先确认是否保存，保存后再确认是否启动 Goal mode。
- 默认将 goal 文件保存到项目根的 `.codex/goals/`；无法确定项目根时使用当前工作目录下的 `.codex/goals/`。

是否提交 `.codex/goals/` 由项目决定：个人 goal 通常应加入 `.gitignore`，团队共享的 goal 可以显式纳入版本控制。

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

新安装应始终使用 `skills/goal-workflow/`。根目录兼容镜像由验证脚本强制与 canonical 内容一致，仅用于帮助 0.1.x Git 安装平滑迁移，不应作为新安装入口。

发布历史见 [CHANGELOG.md](CHANGELOG.md)。
