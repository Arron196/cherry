# Neovim Configuration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create and validate a modular Neovim configuration on Windows for Python, Go, C++, and Rust development.

**Architecture:** Use a structured `lazy.nvim` setup with `lua/config`, `lua/plugins`, and `after/lsp` directories. Rely on native Neovim `0.11+` LSP APIs and Mason-managed language servers.

**Tech Stack:** Neovim `0.12`, Lua, `lazy.nvim`, `blink.cmp`, `mason.nvim`, `nvim-lspconfig`, `conform.nvim`, `telescope.nvim`, `nvim-treesitter`

---

### Task 1: Create the core config skeleton

**Files:**
- Create: `C:\Users\benja\AppData\Local\nvim\init.lua`
- Create: `C:\Users\benja\AppData\Local\nvim\lua\config\options.lua`
- Create: `C:\Users\benja\AppData\Local\nvim\lua\config\keymaps.lua`
- Create: `C:\Users\benja\AppData\Local\nvim\lua\config\autocmds.lua`
- Create: `C:\Users\benja\AppData\Local\nvim\lua\config\lazy.lua`

- [ ] Write the entrypoint and bootstrap files.
- [ ] Add sensible Windows-friendly defaults for editing, search, splits, undo, and clipboard.
- [ ] Add general keymaps that do not depend on any plugin.
- [ ] Add small autocommands for yank highlighting, cursor restore, and Go indentation.
- [ ] Start Neovim headless once to confirm the config loads.

### Task 2: Add UI and editing plugins

**Files:**
- Create: `C:\Users\benja\AppData\Local\nvim\lua\plugins\colorscheme.lua`
- Create: `C:\Users\benja\AppData\Local\nvim\lua\plugins\ui.lua`
- Create: `C:\Users\benja\AppData\Local\nvim\lua\plugins\editor.lua`
- Create: `C:\Users\benja\AppData\Local\nvim\lua\plugins\telescope.lua`
- Create: `C:\Users\benja\AppData\Local\nvim\lua\plugins\treesitter.lua`

- [ ] Add plugin specs grouped by responsibility.
- [ ] Configure Telescope to use `rg --files` so it works even when `fd` is absent.
- [ ] Configure Treesitter for the user's main languages plus Lua and docs.
- [ ] Bootstrap plugins with a headless `Lazy` sync.
- [ ] Re-open headless Neovim to confirm UI plugin setup does not error.

### Task 3: Add completion, LSP, and formatting

**Files:**
- Create: `C:\Users\benja\AppData\Local\nvim\lua\plugins\lsp.lua`
- Create: `C:\Users\benja\AppData\Local\nvim\after\lsp\lua_ls.lua`
- Create: `C:\Users\benja\AppData\Local\nvim\after\lsp\basedpyright.lua`
- Create: `C:\Users\benja\AppData\Local\nvim\after\lsp\ruff.lua`
- Create: `C:\Users\benja\AppData\Local\nvim\after\lsp\gopls.lua`
- Create: `C:\Users\benja\AppData\Local\nvim\after\lsp\clangd.lua`
- Create: `C:\Users\benja\AppData\Local\nvim\after\lsp\rust_analyzer.lua`

- [ ] Add `blink.cmp`, Mason, native LSP setup, diagnostics, and LSP keymaps.
- [ ] Ensure Mason installs the required language servers.
- [ ] Configure Conform to prefer external formatters and fall back to LSP formatting.
- [ ] Validate that Neovim starts headless after plugin installation.

### Task 4: Smoke-test the finished setup

**Files:**
- Verify only: `C:\Users\benja\AppData\Local\nvim\**`

- [ ] Run `C:\Program Files\Neovim\bin\nvim.exe --headless "+Lazy! sync" +qa`.
- [ ] Run `C:\Program Files\Neovim\bin\nvim.exe --headless "+checkhealth lazy" +qa`.
- [ ] Run `C:\Program Files\Neovim\bin\nvim.exe --headless "+checkhealth vim.lsp" +qa`.
- [ ] Summarize any remaining toolchain gaps separately from configuration errors.
