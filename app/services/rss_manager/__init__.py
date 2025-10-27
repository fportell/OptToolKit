"""
RSS Manager Service Package.

Provides RSS subscription management functionality integrated into OpsToolKit.
"""

from .rss_service import get_rss_service, RSSService

__all__ = ['get_rss_service', 'RSSService']
