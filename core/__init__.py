"""
Islamweb Fatawa Scraper & Exporter Core Package
"""
from core.scraper import IslamwebScraper, FatwaItem
from core.formatter import FatwaHTMLFormatter
from core.exporter import FatwaExporter

__all__ = ["IslamwebScraper", "FatwaItem", "FatwaHTMLFormatter", "FatwaExporter"]

