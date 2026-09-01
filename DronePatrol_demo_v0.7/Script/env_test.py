import sys
import platform

sys.stdout.reconfigure(encoding='utf-8')

print("Python 解释器基本信息")
print("-" * 30)
print(f"版本: {sys.version}")
print(f"版本信息: {sys.version_info}")
print(f"可执行文件路径: {sys.executable}")
print(f"操作系统平台: {sys.platform}")
print(f"系统架构: {platform.machine()}")
print(f"处理器: {platform.processor()}")
print(f"操作系统名称: {platform.system()} {platform.release()}")
print(f"Python 实现: {platform.python_implementation()}")