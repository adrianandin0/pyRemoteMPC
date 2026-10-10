import os
from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))

readme_path = os.path.join(here, "README.md")
long_description = ""
if os.path.exists(readme_path):
    with open(readme_path, encoding="utf-8") as f:
        long_description = f.read()

setup(
    name="pyremotempc",
    version="1.0.0",
    description="Native Python mRemoteNG clone for Linux (KDE/GNOME/XFCE) with legacy SSH and RDP engines",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Antigravity Team",
    license="MIT",
    packages=find_packages(),
    package_data={
        "pyremotempc": ["ui/iconos/*.png"],
    },
    include_package_data=True,
    python_requires=">=3.8",
    install_requires=[
        "PySide6>=6.5.0",
        "cryptography>=41.0.0",
        "paramiko>=3.0.0",
        "pyte>=0.8.0",
        "pyserial>=3.5",
        "pyyaml>=6.0",
    ],
    entry_points={
        "console_scripts": [
            "pyremotempc=pyremotempc.app:main",
        ],
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: System Administrators",
        "Intended Audience :: Information Technology",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: System :: Systems Administration",
        "Topic :: Utilities",
    ],
)
