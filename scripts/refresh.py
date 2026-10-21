#!/usr/bin/env python3
"""Invalidate expired caches and force fresh Details; dry run by default."""
from enrich import main

if __name__ == '__main__':
    main(force=True)
