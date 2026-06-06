# 打包流程与原理

## 打包原理（三层合一）

你的源码由三部分组成，打包过程也分三步：

```
                        你的源码
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
     Web 前端          Python 后端        Tauri 壳
   (HTML/CSS/JS)    (FastAPI+代理)    (Rust 窗口)
          │                │                │
          ▼                ▼                ▼
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    直接复制到   PyInstaller 打包成   Cargo 编译成
    distDir/     localswitch-backend.exe   localswitch.exe
          │                │                │
          └────────────────┼────────────────┘
                           ▼
                   Tauri Bundler 打包
                    (WIX/MSI + NSIS)
                           │
                ┌──────────┴──────────┐
                ▼                     ▼
            .msi 安装包           .exe 安装包
```

### 细节

**第一步：PyInstaller 打包 Python**
```
python build.py
```
- 把 `main.py` + `backend/` + `src/` + 所有 Python 依赖（fastapi、uvicorn、httpx...）塞进一个 `localswitch-backend.exe`
- 用户不需要装 Python，这个 exe 自带 Python 解释器和所有库
- 结果：`dist/localswitch-backend.exe`（~10MB）

**第二步：Rust 编译 Tauri**
```
cargo build --release
```
- 把 `src-tauri/src/main.rs` 编译成 `localswitch.exe`
- 内嵌 WebView2 渲染引擎（Windows 自带）
- Rust 代码负责：创建窗口、**启动 Python 后端 sidecar**、关闭时终止

**第三步：Tauri Bundler 打包安装包**
```
cargo tauri build
```
- 把 localswitch.exe + localswitch-backend.exe + 前端文件 + 图标 打包
- 用 WIX 生成 `.msi`（Windows 标准安装）
- 用 NSIS 生成 `.exe`（自解压安装）

**安装后的目录结构：**
```
C:\Program Files\LocalSwitch\
├── localswitch.exe              ← 主程序（Rust 编译）
├── localswitch-backend.exe      ← Python 后端（PyInstaller 打包）
├── src\                         ← 前端文件
│   ├── index.html
│   ├── style.css
│   └── main.js
└── icons\
```

**启动流程：**
```
用户双击 localswitch.exe
  │
  ├→ Rust 创建窗口 + WebView
  ├→ Rust 自动启动 localswitch-backend.exe（spawn 子进程）
  │     └→ Python 启动 FastAPI（端口 8318, 8317）
  ├→ WebView 加载前端页面，通过 localhost:8318 调后端 API
  │
用户关闭窗口
  ├→ Rust 发送 kill 信号给 Python 进程
  └→ 窗口销毁
```

**为什么不需要安装任何依赖？**
| 依赖 | 处理方式 |
|------|---------|
| Python 解释器 | PyInstaller 内嵌 Python 3.7（约 4MB） |
| fastapi/uvicorn/httpx | PyInstaller 打包进 exe |
| Rust 运行时 | 静态链接到 localswitch.exe |
| WebView2 | Windows 10/11 自带 |
| Visual C++ 运行时 | 系统自带 |

## 修改源码后如何重新打包

### 修改了哪个部分？

```
d:\localswitch\
├── src/              ← 改前端 HTML/CSS/JS 的话：
│   ├── index.html         python build.py → cargo tauri build
│   ├── style.css
│   └── main.js
│
├── backend/          ← 改 Python 后端的话：
│   └── api_server.py      python build.py → cargo tauri build
│
├── proxy_server.py   ← 改代理逻辑的话：
├── protocol_adapter.py    python build.py → cargo tauri build
│
├── config.py         ← 改配置逻辑：
│                         python build.py → cargo tauri build
│
├── src-tauri\src\    ← 改 Rust/窗口/系统逻辑的话：
│   └── main.rs            cargo tauri build
│
└── src-tauri\tauri.conf.json  ← 改窗口大小/图标/打包等：
                                    cargo tauri build
```

### 完整打包命令（三步）

```powershell
# 1. 打包 Python 后端为 exe
cd d:\localswitch
python build.py

# 2. 拷贝 sidecar 并改名
copy dist\localswitch-backend.exe src-tauri\binaries\localswitch-backend-x86_64-pc-windows-msvc.exe

# 3. 打包为安装程序
cd src-tauri
cargo tauri build
```

**输出位置：**
```
src-tauri\target\release\bundle\
├── msi\localswitch_1.0.0_x64_en-US.msi   ← MSI 安装包（推荐）
└── nsis\localswitch_1.0.0_x64-setup.exe   ← NSIS 安装包
```

### 快速迭代（只改前端，不重新打包）

如果只改了 `src/*`，不需要重新打包，直接替换已安装目录下的文件即可：
```powershell
copy src\* "C:\Program Files\LocalSwitch\src\"
```

### 只编译 exe 不生成安装包（调试用）

```powershell
cd d:\localswitch

# 1. 重新打包 Python
python build.py

# 2. 只编译 Rust
cd src-tauri
cargo build --release

# 结果：target\release\localswitch.exe（不包含安装包）
```

## 版本号

修改 `src-tauri\tauri.conf.json` 中的 `version` 字段，然后重新 `cargo tauri build`，安装包文件名会自动更新。
