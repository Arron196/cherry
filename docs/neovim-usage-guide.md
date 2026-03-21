# Neovim 使用说明

这份文档说明当前这台机器上已经配置好的 Neovim 能做什么，以及日常该怎么用。

## 1. 当前已经配置好的内容

这次配置完成后，你的环境已经具备下面这些能力：

- 直接在终端里输入 `nvim` 启动 Neovim
- Windows Terminal 默认字体已切到 `Maple Mono NF CN`
- 使用 `lazy.nvim` 管理插件
- 使用 `tokyonight` 主题
- 使用 `telescope` 做文件搜索和全文搜索
- 使用 `nvim-treesitter` 做语法高亮和更好的缩进支持
- 使用 `which-key` 显示快捷键提示
- 使用 `lualine` 显示状态栏
- 使用 `gitsigns` 在左侧显示 Git 改动标记
- 使用 `neo-tree` 在左侧显示项目文件树
- 使用 `Comment.nvim`、`nvim-autopairs`、`nvim-surround` 提升编辑体验
- 使用 `blink.cmp` 做补全
- 使用 `mason + lspconfig` 管理和启动语言服务器
- 使用 `conform.nvim` 做格式化
- 使用 `neoscroll.nvim` 做平滑滚动
- 使用 `smear-cursor.nvim` 做光标拖影动画
- 使用底部终端分窗一键运行当前文件

## 2. 已支持的语言

当前已经给下面几类语言配好了 LSP 和格式化：

- Python: `basedpyright` + `ruff`
- Go: `gopls`
- C/C++: `clangd`
- Rust: `rust-analyzer`
- Lua: `lua_ls`

格式化规则如下：

- Python: `ruff format`
- Go: `goimports` / `gofmt`
- Rust: `rustfmt`
- C/C++: `clang-format`
- Lua: `stylua`

其中大部分文件会在保存时自动格式化。

## 3. 怎么启动

常用启动方式：

```powershell
nvim
nvim .
nvim path\to\file.py
```

推荐的日常用法：

- `nvim .` 打开当前项目目录
- `nvim 文件名` 直接编辑某个文件
- 在项目根目录启动，这样 LSP、搜索、Git 都更稳定

## 4. 你需要先知道的一个约定

当前配置的 `<leader>` 是空格键，也就是：

- `<leader>w` 的意思是先按空格，再按 `w`
- `<leader>ff` 的意思是先按空格，再按两次 `f`

## 5. 最常用的基础键位

### 保存和退出

- `<leader>w`: 保存当前文件
- `<leader>q`: 退出当前窗口
- `<leader>Q`: 强制退出全部窗口
- `<Esc>`: 清除搜索高亮

### 文件树和 buffer 切换

- `<leader>e`: 打开/关闭左侧文件树
- `<S-h>`: 切到上一个 buffer
- `<S-l>`: 切到下一个 buffer

### 分屏和运行

- `<leader>sh`: 水平分屏
- `<leader>sv`: 垂直分屏
- `<leader>so`: 只保留当前窗口
- `<leader>se`: 平均分配窗口大小
- `<leader>ru`: 在底部终端运行当前文件

### 窗口切换

- `<C-h>`: 切到左边窗口
- `<C-j>`: 切到下面窗口
- `<C-k>`: 切到上面窗口
- `<C-l>`: 切到右边窗口

### 窗口缩放

- `<C-Up>`: 增加当前窗口高度
- `<C-Down>`: 减少当前窗口高度
- `<C-Left>`: 减少当前窗口宽度
- `<C-Right>`: 增加当前窗口宽度

### 行号显示

- `<leader>un`: 切换相对行号开关

## 6. 原生 Vim 快速跳转

这一节说的是不依赖任何插件、Neovim 原生就有的高频跳转能力。

这些键一旦熟了，效率会非常高。

### 行内跳转

- `0`: 跳到本行最开头
- `^`: 跳到本行第一个非空白字符
- `$`: 跳到本行末尾

### 单词跳转

- `w`: 跳到下一个单词开头
- `b`: 跳到上一个单词开头
- `e`: 跳到当前或下一个单词结尾

### 文件内大范围跳转

- `gg`: 跳到文件第一行
- `G`: 跳到文件最后一行
- `数字 + G`: 跳到指定行，例如 `20G`

### 括号和配对符跳转

- `%`: 在成对的括号、方括号、大括号之间来回跳

这个对 Python、C++、Rust、Go 里看函数块和条件块特别有用。

### 字符级快速定位

- `f{字符}`: 跳到本行右侧下一个指定字符
- `F{字符}`: 跳到本行左侧上一个指定字符
- `t{字符}`: 跳到本行右侧指定字符前一位
- `T{字符}`: 跳到本行左侧指定字符后一位
- `;`: 重复上一次 `f/F/t/T`
- `,`: 反方向重复上一次 `f/F/t/T`

例如：

- `f(`: 跳到本行下一个 `(`
- `t,`: 跳到下一个逗号前面

### 搜索跳转

- `/关键词`: 向下搜索
- `?关键词`: 向上搜索
- `n`: 跳到下一个搜索结果
- `N`: 跳到上一个搜索结果
- `*`: 搜索当前光标下的单词并跳到下一个
- `#`: 搜索当前光标下的单词并跳到上一个

### 跳转历史

- `<C-o>`: 回到上一次跳转前的位置
- `<C-i>`: 前进到下一次跳转位置

这个在你 `gd` 跳到定义之后非常好用：

1. `gd` 进去看定义
2. `<C-o>` 回到原来位置

### 标记跳转

- `m{字母}`: 在当前位置打一个 mark
- `'{字母}`: 跳到该 mark 所在行
- `` `{字母}` ``: 精确跳到该 mark 所在列

例如：

- `ma`: 给当前位置打一个 `a` 标记
- `'a`: 跳回标记 `a`

### 屏幕滚动相关

- `<C-u>`: 向上滚半屏
- `<C-d>`: 向下滚半屏
- `<C-b>`: 向上翻一整屏
- `<C-f>`: 向下翻一整屏
- `zz`: 把当前行滚到屏幕中间
- `zt`: 把当前行滚到屏幕顶部
- `zb`: 把当前行滚到屏幕底部

现在你这套配置已经给这些滚动动作加了平滑动画，所以看起来会更丝滑。

## 7. 搜索和文件查找

这是你以后最常用的一组键：

- `<leader>ff`: 查找文件
- `<leader>fg`: 全文搜索
- `<leader>fb`: 查看当前 buffer 列表
- `<leader>fr`: 查看最近打开过的文件
- `<leader>fh`: 搜索帮助文档

说明：

- `find files` 会搜索隐藏文件，但默认排除 `.git`
- `live grep` 依赖 `rg`，你的机器上已经有了
- 如果你更想像 VS Code 一样浏览项目结构，用 `<leader>e` 打开左侧文件树

## 8. 文件树怎么用

文件树由 `neo-tree` 提供。

最常用的打开方式：

- `<leader>e`: 开关左侧文件树
- `:Neotree filesystem reveal left`: 在左侧打开文件树并定位当前文件

常见使用方式：

- 用方向键或 `j` / `k` 上下移动
- 在目录上按回车展开或折叠
- 在文件上按回车打开文件
- 在文件树窗口里按 `?` 查看它自己的帮助键位

适合你的日常流程：

1. 在项目根目录执行 `nvim .`
2. 按 `<leader>e`
3. 左边看目录树，右边看代码
4. 需要时再配合 `<leader>ff` 和 `<leader>fg`

## 9. LSP 代码导航怎么用

打开 Python、Go、C/C++、Rust、Lua 文件后，LSP 会自动启动。

最常用的键位：

- `gd`: 跳到定义
- `gD`: 跳到声明
- `gi`: 跳到实现
- `gr`: 查找引用
- `K`: 查看光标处符号说明
- `<leader>ca`: 代码操作，例如导入、修复、重构建议
- `<leader>cr`: 重命名符号
- `<leader>cd`: 查看当前行诊断信息
- `[d`: 跳到上一个诊断
- `]d`: 跳到下一个诊断

### 一个典型例子

如果你在 Python 代码里看到某个函数：

1. 把光标放到函数名上
2. 按 `gd` 跳到定义
3. 按 `gr` 看这个函数在哪里被调用
4. 按 `K` 看说明
5. 如果要统一改名，按 `<leader>cr`

## 10. 补全怎么用

补全由 `blink.cmp` 提供。

你会得到这些行为：

- 进入插入模式后会自动弹出候选
- 文档说明会自动显示
- 按 `<C-space>` 可以手动呼出补全菜单

如果菜单弹出，通常可以继续使用你熟悉的回车、方向键、Tab 进行选择；不同终端下细节可能略有差别，但自动补全本身已经可用。

## 11. 格式化怎么用

### 自动格式化

大多数支持的语言在保存时会自动格式化。

也就是说，平时你只要：

1. 写代码
2. 按 `<leader>w`

通常就会顺手完成保存和格式化。

### 手动格式化

- `<leader>cf`: 手动格式化当前文件

如果你不确定当前文件会调用哪个格式化器，可以执行：

```vim
:ConformInfo
```

## 12. 注释、括号和包围编辑

### 注释

`Comment.nvim` 已经启用，常用方法：

- `gcc`: 注释/取消注释当前行
- 视觉模式选中多行后按 `gc`: 注释/取消注释选中内容

### 自动补全括号

`nvim-autopairs` 已启用，所以输入：

- `(`
- `[`
- `{`
- `'`
- `"`

时，通常会自动补全右半边。

### 包围编辑

`nvim-surround` 已启用，常见例子：

- `ysiw"`: 给当前单词加上双引号
- `cs"'`: 把双引号改成单引号
- `ds"`: 删除包围当前内容的双引号

## 13. Git 和改动导航

`gitsigns` 已启用。

你会在编辑器左侧看到 Git 改动标记：

- `+`: 新增
- `~`: 修改
- `_` / `-`: 删除

现在还额外绑定了这些快捷键：

- `]g`: 跳到下一个 Git hunk
- `[g`: 跳到上一个 Git hunk
- `<leader>gp`: 预览当前 hunk
- `<leader>gr`: 重置当前 hunk
- `<leader>gB`: 查看当前行 blame

如果你想知道一段代码到底改了什么，最常用的就是：

1. 把光标放到那一段附近
2. 按 `<leader>gp` 预览修改块
3. 如果只是自己临时改坏了，按 `<leader>gr` 回退当前 hunk
4. 如果想看是谁改的，按 `<leader>gB`

## 14. 动画效果怎么用

这次加了两种动画：

- `neoscroll.nvim`: 平滑滚动
- `smear-cursor.nvim`: 光标拖影动画

### 平滑滚动

你平时这些动作现在会更丝滑：

- `<C-u>`
- `<C-d>`
- `<C-b>`
- `<C-f>`
- `zz`
- `zt`
- `zb`

也就是说，整页上下移动和重新居中不再是“瞬间跳过去”，而是平滑过渡。

### 光标拖影动画

这个是你看到的“光标上下移动时带拖影”的效果。

默认已经开启，如果你想临时开关它，可以执行：

```vim
:SmearCursorToggle
```

## 15. 终端模式怎么用

如果你在 Neovim 里打开终端：

```vim
:terminal
```

退出终端输入模式的方法：

- `<Esc><Esc>`

这样会从终端输入态回到普通模式。

## 16. 当前文件一键运行

你现在可以用：

- `<leader>ru`
- `:RunCurrentFile`

来运行当前文件。

运行时会发生这些事：

1. 先自动保存当前文件
2. 在底部打开一个终端分窗
3. 在这个分窗里执行对应语言的运行命令

当前支持：

- Python: `python 当前文件.py`
- Go: 在当前文件目录执行 `go run .`
- Rust:
  - 如果项目里有 `Cargo.toml`，执行 `cargo run`
  - 否则编译当前文件再运行
- C: 编译当前文件再运行
- C++: 编译当前文件再运行
- Lua: `lua 当前文件.lua`

说明：

- 这个快捷键更适合“当前文件/当前目录可直接运行”的场景
- 如果当前文件本身不是入口文件，运行失败是正常的
- Go 和 Rust 项目里，建议在真正的入口文件所在目录或 Cargo 项目里使用

## 17. 分屏开发怎么用

你现在已经有一套更适合项目开发的分屏键位：

- `<leader>sh`: 上下分屏
- `<leader>sv`: 左右分屏
- `<leader>so`: 只保留当前窗口
- `<leader>se`: 把所有窗口重新平均分配

一个典型工作流：

1. `nvim .`
2. `<leader>e` 打开文件树
3. `<leader>sv` 打开右侧代码窗口
4. `<leader>sh` 在底部开一个窗口
5. `<leader>ru` 在底部终端运行当前文件
6. `<C-h/j/k/l>` 在窗口间移动
7. `<C-Up/Down/Left/Right>` 微调窗口大小

## 18. 已经设置好的默认行为

当前配置里还有一些会自动生效的小细节：

- 开启绝对行号和相对行号
- 支持系统剪贴板
- 搜索默认忽略大小写，输入大写时自动切换为大小写敏感
- 光标行高亮
- 分屏默认右开、下开
- 关闭自动换行
- 打开撤销文件
- 复制文字后自动高亮一下
- 重新打开文件时会尽量回到上次离开的位置
- Go 文件默认使用 tab 而不是空格缩进

## 19. 常用命令

除了快捷键，你也会经常用到这些命令：

```vim
:Mason
:Lazy
:Telescope
:ConformInfo
:Neotree
:RunCurrentFile
:SmearCursorToggle
:TutorZh
:TutorZh2
:checkhealth
:checkhealth neo-tree
:checkhealth mason
:checkhealth vim.lsp
:terminal
```

可以这样理解：

- `:Mason`: 看语言服务器和工具有没有安装好
- `:Lazy`: 看插件状态
- `:ConformInfo`: 看格式化器状态
- `:Neotree`: 打开文件树
- `:RunCurrentFile`: 在底部终端运行当前文件
- `:SmearCursorToggle`: 开关光标拖影动画
- `:TutorZh`: 打开中文第一课 tutor
- `:TutorZh2`: 打开中文第二课 tutor
- `:checkhealth`: 做整体健康检查
- `:checkhealth neo-tree`: 专查文件树
- `:checkhealth mason`: 专查 Mason
- `:checkhealth vim.lsp`: 专查 LSP

## 20. 配置文件都在哪里

主配置目录：

```text
C:\Users\benja\AppData\Local\nvim
```

比较重要的文件：

- `C:\Users\benja\AppData\Local\nvim\init.lua`
- `C:\Users\benja\AppData\Local\nvim\lua\config\commands.lua`
- `C:\Users\benja\AppData\Local\nvim\lua\config\options.lua`
- `C:\Users\benja\AppData\Local\nvim\lua\config\keymaps.lua`
- `C:\Users\benja\AppData\Local\nvim\lua\plugins\explorer.lua`
- `C:\Users\benja\AppData\Local\nvim\lua\plugins\lsp.lua`
- `C:\Users\benja\AppData\Local\nvim\lua\plugins\motion.lua`
- `C:\Users\benja\AppData\Local\nvim\lua\plugins\telescope.lua`
- `C:\Users\benja\AppData\Local\nvim\lua\plugins\treesitter.lua`
- `C:\Users\benja\AppData\Local\nvim\after\lsp\`

其中：

- `lua/config/` 放基础设置
- `lua/plugins/` 放插件配置
- `after/lsp/` 放每种语言的单独 LSP 设置

## 21. 推荐你的日常使用流程

如果你是在一个项目里写代码，可以按这个顺序用：

1. 在项目根目录打开终端
2. 输入 `nvim .`
3. 按 `<leader>e` 打开左侧文件树
4. 用 `<leader>sv` 或 `<leader>sh` 打开分屏
5. 用 `<leader>ff` 找文件
6. 用 `<leader>fg` 搜项目里的文本
7. 用 `<S-h>` / `<S-l>` 在已打开文件之间切换
8. 写代码时用 `gd`、`gr`、`K` 做跳转和查看
9. 需要修复建议时用 `<leader>ca`
10. 需要重命名时用 `<leader>cr`
11. 想看当前改动时用 `<leader>gp`
12. 运行当前文件时按 `<leader>ru`
13. 保存时按 `<leader>w`
14. 如果想手动格式化，再按 `<leader>cf`

## 22. 遇到问题时先怎么排查

### `nvim` 命令找不到

先关掉当前终端，再开一个新终端。

### 补全、LSP、格式化不工作

优先检查：

```vim
:Mason
:checkhealth vim.lsp
:ConformInfo
```

### 插件不正常

执行：

```vim
:Lazy
:checkhealth
:checkhealth neo-tree
```

### 字体不正常

如果 Windows Terminal 没有立即显示 `Maple Mono NF CN`：

1. 彻底关闭全部 Windows Terminal 窗口
2. 重新打开
3. 如果还不行，注销一次 Windows 账户再登录

## 23. 这套配置目前适合什么场景

它现在已经很适合下面这些用途：

- 日常 Python 开发
- Go 项目开发
- C/C++ 代码阅读和编辑
- Rust 开发
- Lua 配置编辑
- 在项目里快速搜索、跳转、补全、格式化

它目前还没有加的内容包括：

- Debugger
- 测试运行快捷键
- 更重型的 UI 组件

如果后面你想继续扩展，这几个方向都可以再加。

## 24. 一句话总结

现在这套 Neovim 已经能满足你在 Windows 上做 Python、Go、C++、Rust 日常开发的核心需求：

- 能搜索
- 能补全
- 能跳转
- 能报错提示
- 能格式化
- 能看 Git 改动
- 能看左侧文件树
- 能分屏开发
- 能一键运行当前文件
- 能丝滑滚动和光标动画
- 能直接在终端里启动

如果你后面还想升级，我建议下一步优先加：

1. Debugger
2. 测试运行快捷键
3. 终端快捷键
4. 调试相关快捷键
