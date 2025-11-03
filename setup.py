"""
Setup script for vLLM Batch Server.

Installs the CLI as 'vllm-batch' command.
"""

from setuptools import setup, find_packages

setup(
    name='vllm-batch-server',
    version='1.0.0',
    description='Local vLLM batch processing server with Label Studio integration',
    author='vLLM Batch Server Contributors',
    packages=find_packages(),
    install_requires=[
        'click>=8.0.0',
        'requests>=2.28.0',
    ],
    entry_points={
        'console_scripts': [
            'vllm-batch=core.cli:cli',
        ],
    },
    python_requires='>=3.9',
)

