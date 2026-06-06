#!/usr/bin/env python
"""
LocalSwitch 打包脚本
将 Python 后端打包为 exe，作为 Tauri 的 sidecar
"""
import os
import sys
import shutil
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def clean():
    """清理旧的构建文件"""
    for d in ['build', 'dist', '__pycache__']:
        path = os.path.join(BASE_DIR, d)
        if os.path.exists(path):
            shutil.rmtree(path)
    for f in ['localswitch-backend.spec']:
        path = os.path.join(BASE_DIR, f)
        if os.path.exists(path):
            os.remove(path)
    print("Cleaned old build files")


def build():
    """用 PyInstaller 打包 Python 后端"""
    # 确保 backend 目录存在
    if not os.path.exists(os.path.join(BASE_DIR, 'backend')):
        print("ERROR: backend/ directory not found")
        sys.exit(1)

    # 构建命令
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',
        '--name', 'localswitch-backend',
        '--distpath', os.path.join(BASE_DIR, 'dist'),
        '--workpath', os.path.join(BASE_DIR, 'build'),
        '--specpath', BASE_DIR,
        # 隐藏导入（PyInstaller 无法自动检测的模块）
        '--hidden-import', 'uvicorn',
        '--hidden-import', 'uvicorn.logging',
        '--hidden-import', 'uvicorn.loops',
        '--hidden-import', 'uvicorn.loops.auto',
        '--hidden-import', 'uvicorn.protocols',
        '--hidden-import', 'uvicorn.protocols.http',
        '--hidden-import', 'uvicorn.protocols.websockets',
        '--hidden-import', 'uvicorn.lifespan',
        '--hidden-import', 'uvicorn.lifespan.on',
        '--hidden-import', 'fastapi',
        '--hidden-import', 'fastapi.openapi',
        '--hidden-import', 'fastapi.middleware.cors',
        '--hidden-import', 'fastapi.middleware',
        '--hidden-import', 'fastapi.responses',
        '--hidden-import', 'fastapi.exceptions',
        '--hidden-import', 'pydantic',
        '--hidden-import', 'pydantic.deprecated.decorator',
        '--hidden-import', 'httpx',
        '--hidden-import', 'httpcore',
        '--hidden-import', 'starlette',
        '--hidden-import', 'starlette.middleware',
        '--hidden-import', 'starlette.routing',
        '--hidden-import', 'starlette.responses',
        '--hidden-import', 'starlette.exceptions',
        '--hidden-import', 'anyio',
        '--hidden-import', 'anyio._backends',
        '--hidden-import', 'anyio._backends._asyncio',
        '--hidden-import', 'click',
        '--hidden-import', 'h11',
        '--hidden-import', 'idna',
        '--hidden-import', 'sniffio',
        '--hidden-import', 'certifi',
        '--hidden-import', 'charset_normalizer',
        # 数据文件
        '--add-data', f'{os.path.join(BASE_DIR, "backend")}{os.pathsep}backend',
        '--add-data', f'{os.path.join(BASE_DIR, "src")}{os.pathsep}src',
        # 入口文件
        os.path.join(BASE_DIR, 'main.py'),
    ]

    print("Building Python backend with PyInstaller...")
    print(f"Command: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=BASE_DIR)
    if result.returncode != 0:
        print("Build failed!")
        sys.exit(1)

    print("Build completed successfully!")
    exe_path = os.path.join(BASE_DIR, 'dist', 'localswitch-backend.exe')
    if os.path.exists(exe_path):
        size_mb = os.path.getsize(exe_path) / 1024 / 1024
        print(f"Output: {exe_path} ({size_mb:.1f} MB)")


def copy_to_tauri():
    """将打包好的 exe 复制到 Tauri sidecar 目录"""
    src = os.path.join(BASE_DIR, 'dist', 'localswitch-backend.exe')
    dst_dir = os.path.join(BASE_DIR, 'src-tauri', 'binaries')
    dst = os.path.join(dst_dir, 'localswitch-backend.exe')

    if not os.path.exists(src):
        print(f"ERROR: {src} not found. Run build first.")
        sys.exit(1)

    os.makedirs(dst_dir, exist_ok=True)
    shutil.copy2(src, dst)
    print(f"Copied to: {dst}")


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'clean':
        clean()
    else:
        clean()
        build()
        copy_to_tauri()
        print("\nAll done! Now run 'cargo tauri build' to create the installer.")
