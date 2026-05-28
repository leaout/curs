# coding: utf-8
"""
curs_main.py - 兼容壳，重定向到 run.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run import main

if __name__ == "__main__":
    main()
