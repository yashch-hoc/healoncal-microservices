"""
API Endpoints Package

This package contains all API endpoint modules for the application.
"""

# Import routers to make them available when importing from this package
from .healoncal_analysis import router as healoncal_router

__all__ = ["healoncal_router"]
