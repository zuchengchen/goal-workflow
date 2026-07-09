# Changelog

本项目的显著变更记录在此文件中，版本号遵循 Semantic Versioning。

## [Unreleased]

## [0.2.0] - 2026-07-10

### Added

- 增加版本文件、变更记录和 MIT License。
- 增加自动化结构检查、场景化行为契约、隔离安装烟测和 CI 发布验证。
- 为安装、更新、卸载、同名冲突和旧安装迁移提供可执行说明。

### Changed

- 将 canonical 可安装 skill 从仓库根迁移到 `skills/goal-workflow/`。仓库根在 0.2.x 保留受自动校验的兼容镜像，旧安装仍可运行，但新安装和长期更新应迁移到 canonical 路径。
- 安装地址现在明确固定 ref 和 path；moving ref 为 `master`，path 为 `skills/goal-workflow`。可复现安装默认建议使用版本 tag 或完整 commit SHA。
- skill 改为完全自包含，不再依赖或调用外部 `$define-goal`。
- 新 goal 文件默认保存到项目根 `.codex/goals/`；无法确定项目根时保存到当前工作目录下的 `.codex/goals/`，以避免污染仓库根。
- 将历史 goal 文档移入 `docs/history/`，不再随 canonical skill 安装。
- README 精简为项目入口，详细安装和迁移规则统一由 `INSTALL.md` 维护。

### Fixed

- 修复安装器因默认 `main`、仓库根路径或隐式推断而失败的问题。
- 修复项目级复制示例创建了源目录而非目标目录的问题。
- 明确安装器遇到同名目录时停止，以及更新时避免增量覆盖残留文件。
- 保留用户显式请求的 `token_budget`，并在恢复执行时从已保存的 goal 文件中恢复该选项。

### Migration

- 0.1.x 仓库根安装应先备份旧目录，再从 `skills/goal-workflow/` 全新安装。0.2.x 的根镜像允许旧 Git 安装过渡运行，但不作为长期安装接口。
- 已有根目录 goal 文件不会自动移动。个人 goal 可迁移到 `.codex/goals/` 并加入 `.gitignore`；团队共享 goal 可审阅后显式提交。
