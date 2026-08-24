#!/usr/bin/env python3
"""
GridTrader CLI Entry Point

Install as command-line tool:
    pip install -e .
    
Then use:
    gridtrader-cli list
    gridtrader-cli start MyStrategy
"""

from gridtrader.api.cli.client import main

if __name__ == '__main__':
    main()
