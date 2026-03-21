# Neovim Configuration Design

## Goal

Build a modular Neovim configuration for Windows that follows the structure from MartinLwx's tutorial while adding practical defaults for Python, Go, C++, and Rust development.

## Constraints

- Target Neovim version: `0.12.0`
- Config directory: `C:\Users\benja\AppData\Local\nvim`
- The editor executable currently exists at `C:\Program Files\Neovim\bin\nvim.exe`
- `nvim` is not currently on the shell `PATH`, so validation should use the absolute executable path
- Existing repository changes in `C:\学校\cherry` must remain untouched

## Architecture

The configuration will use the tutorial's structured layout:

- `init.lua` as a thin entrypoint
- `lua/config/` for core options, keymaps, autocommands, and `lazy.nvim` bootstrap
- `lua/plugins/` for grouped plugin specs
- `after/lsp/` for per-server native LSP overrides

This keeps the setup close to the tutorial while aligning with Neovim `0.11+` guidance around `vim.lsp.config()` / `vim.lsp.enable()`.

## Plugin Stack

- Plugin manager: `folke/lazy.nvim`
- Theme: `folke/tokyonight.nvim`
- Search/navigation: `nvim-telescope/telescope.nvim`
- Syntax parsing: `nvim-treesitter/nvim-treesitter`
- UI/helpers: `which-key.nvim`, `lualine.nvim`, `gitsigns.nvim`, `indent-blankline.nvim`
- Editing ergonomics: `Comment.nvim`, `nvim-autopairs`, `nvim-surround`
- Completion: `Saghen/blink.cmp`
- LSP/package management: `mason.nvim`, `mason-lspconfig.nvim`, `nvim-lspconfig`
- Formatting: `stevearc/conform.nvim`
- Lua config support: `folke/lazydev.nvim`

## Language Support

- Python: `basedpyright` + `ruff`
- Go: `gopls`
- C/C++: `clangd`
- Rust: `rust-analyzer`
- Lua: `lua_ls` for editing the Neovim config itself

Per-server settings will live in `after/lsp/` so they override defaults cleanly.

## Formatting Strategy

Formatting will prefer dedicated formatters when available and fall back to LSP formatting when they are not:

- Python: `ruff_format`, fallback to LSP
- Go: `goimports` / `gofmt`, fallback to LSP
- Rust: `rustfmt`, fallback to LSP
- C/C++: `clang_format`, fallback to LSP
- Lua: `stylua` when available

## Validation

Validation will be done with headless Neovim using the absolute executable path:

1. Bootstrap plugins with `lazy.nvim`
2. Run a non-interactive startup check
3. Inspect `:checkhealth` output relevant to plugin/LSP startup

## Scope

This design covers a clean, maintainable personal config only. It does not change the system `PATH`, install a Nerd Font, or attempt to convert the setup into a full Neovim distribution.
