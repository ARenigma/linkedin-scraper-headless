"""
Data models for the LinkedIn Job Scraper Streamlit App.
"""
from typing import List, Optional
from pydantic import BaseModel, Field

class ScrapeConfig(BaseModel):
    """Configuration for a LinkedIn job scrape operation."""
    keywords: List[str] = Field(..., description="Keywords to search for")
    locations: List[str] = Field(..., description="Locations to search in")
    job_count: Optional[int] = Field(25, description="Maximum number of jobs to collect per combination")
    time_filter_days: int = Field(1, description="Time filter in days")
    username: str = Field(..., description="LinkedIn username")
    password: str = Field(..., description="LinkedIn password")
    headless: bool = Field(True, description="Run browser in headless mode")
    max_workers: int = Field(2, description="Maximum number of parallel workers")

class JobDetails(BaseModel):
    """Details of a scraped LinkedIn job."""
    job_id: str = Field(..., description="LinkedIn job ID")
    job_title: str = Field(..., description="Job title")
    company_name: str = Field(..., description="Company name")
    location: str = Field(..., description="Job location")
    date_posted: str = Field(..., description="Date job was posted")
    job_url: str = Field(..., description="URL to the job posting")
    job_description: Optional[str] = Field(None, description="Full job description")
    scraped_keyword: str = Field(..., description="Keyword used to find this job")
    scraped_location: str = Field(..., description="Location used to find this job")
    employment_type: Optional[str] = Field(None, description="Employment type (full-time, part-time, etc.)")
    experience_level: Optional[str] = Field(None, description="Experience level required")
    industries: Optional[List[str]] = Field(None, description="Industries related to the job")
    
class ScrapingStatus(BaseModel):
    """Status of a scraping operation."""
    status: str = Field(..., description="Current status of the scraping operation")
    total_jobs: int = Field(0, description="Total number of jobs found so far")
    current_keyword: Optional[str] = Field(None, description="Current keyword being processed")
    current_location: Optional[str] = Field(None, description="Current location being processed")
    progress: float = Field(0.0, description="Progress percentage (0-100)")
    error_message: Optional[str] = Field(None, description="Error message if any")
    completed: bool = Field(False, description="Whether scraping is complete") 