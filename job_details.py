import re
from typing import Dict, Tuple, Optional, Any, List
from playwright.sync_api import Page, Locator

from config import logger, SHORT_WAIT

class JobDetailsExtractor:
    """Extract job details from LinkedIn job postings."""
    
    # Regex patterns for salary and job info
    RUPEE_PATTERN = r"(₹[\d,.]+[KlMB]?(?:/yr|/hr|/day|/month)?)(?:\s*-\s*(₹[\d,.]+[KlMB]?(?:/yr|/hr|/day|/month)?))"
    DOLLAR_PATTERN = r"(\$[\d,]+(?:K|M)?(?:/yr|/hr|/day|/month)?)(?:\s*-\s*(\$[\d,]+(?:K|M)?(?:/yr|/hr|/day|/month)?))"
    GENERIC_CURRENCY = r"[₹$€£][\d,.]+(K|M|B)?(/\w+)?(\s*-\s*[₹$€£][\d,.]+(K|M|B)?(/\w+)?)"
    SUSPICIOUS_TERMS = ["premium", "trial", "free", "subscription", "plan"]
    
    # Optimized selectors
    SELECTORS = {
        "job_title": [
            ".job-details-jobs-unified-top-card__job-title",
            "h1.t-24", 
            "h1.job-title"
        ],
        "company_name": [
            ".job-details-jobs-unified-top-card__company-name",
            "a.topcard__org-name-link"
        ],
        "job_location": [
            ".job-details-jobs-unified-top-card__primary-description-container",
            ".job-details-jobs-unified-top-card__bullet",
            "span.topcard__flavor--bullet"
        ],
        "posted_time": [
            ".job-details-jobs-unified-top-card__primary-description-container strong span",
            ".posted-time-ago__text",
            "span.posted-time"
        ],
        "company_url": [
            "div.job-details-jobs-unified-top-card__company-name a",
            "a.topcard__org-name-link"
        ],
        "industry": [
            "div.t-14.mt5",
            "span.company-industries"
        ],
        "employees": [
            "section[data-view-name='job-details-about-company-module'] span.jobs-company__inline-information",
            ".company-employee-count"
        ],
        "hiring_manager": [
            "div.hirer-card__hirer-information a",
            ".posted-by a"
        ],
        "compensation_section": [
            "section:has-text('Compensation')",
            "div.jobs-unified-compensation__container",
            ".salary-range-section"
        ]
    }
    
    def __init__(self):
        self.job_details = {}
        
    def extract(self, page: Page, location: str = "", keyword: str = "") -> Dict[str, Any]:
        """Extract all job details from the current job posting page."""
        # Reset job details
        self.job_details = {
            "Job Title": "Not Specified",
            "Job City": location,
            "Job Profile": keyword,
            "Company Name": "Not Specified",
            "Job Location": "Not Specified",
            "Workplace Type": "Not Specified",
            "Job Type": "Not Specified",
            "Job Budget": "Not Specified",
            "Posted Time": "Not Specified",
            "Total Employees": "Not Specified",
            "Industry": "Not Specified",
            "Company LinkedIn URL": "",
            "Job URL": "",
            "Hiring Manager URL": ""
        }
        
        try:
            # Wait for critical elements to be loaded
            self._wait_for_job_page(page)
            
            # Extract all details in parallel where possible
            self._extract_basic_info(page)
            self._extract_job_card_data(page)
            self._extract_urls_and_company(page)
            self._extract_industry_and_employees(page)
            
        except Exception as e:
            logger.error(f"Error extracting job details: {e}")
            
        return self.job_details
    
    def _wait_for_job_page(self, page: Page) -> None:
        """Wait for critical job page elements to load before extraction."""
        try:
            # Wait for either job title or company name to be visible
            page.wait_for_selector(",".join(self.SELECTORS["job_title"]) + "," + 
                                ",".join(self.SELECTORS["company_name"]),
                                timeout=SHORT_WAIT)
        except Exception:
            # Continue even if timeout, we'll handle missing data gracefully
            pass
            
    def _extract_basic_info(self, page: Page) -> None:
        """Extract basic job info like title, company, location."""
        # Job title - try multiple selectors
        self.job_details["Job Title"] = self._get_from_selectors(page, self.SELECTORS["job_title"])
                
        # Company name   
        self.job_details["Company Name"] = self._get_from_selectors(page, self.SELECTORS["company_name"])
            
        # Job location
        raw_location = self._get_from_selectors(page, self.SELECTORS["job_location"])
        if raw_location:
            # Clean up location text (split by bullet point if present)
            cleaned_location = re.split(r"·|\•", raw_location)[0].strip()
            if cleaned_location:
                # Get first part if comma-separated
                self.job_details["Job Location"] = cleaned_location.split(",")[0].strip()
            
        # Posted time
        posted_text = self._get_from_selectors(page, self.SELECTORS["posted_time"])
        if posted_text:
            self.job_details["Posted Time"] = posted_text
            
    def _get_from_selectors(self, page: Page, selectors: List[str], default: str = "") -> str:
        """Try multiple selectors and return the first successful result."""
        for selector in selectors:
            try:
                element = page.locator(selector)
                if element.count() > 0 and element.first.is_visible(timeout=SHORT_WAIT):
                    content = element.first.text_content(timeout=SHORT_WAIT)
                    if content:
                        return content.strip()
            except Exception:
                continue
        return default
            
    def _extract_job_card_data(self, page: Page) -> None:
        """Extract workplace type, job type and salary data."""
        # Use the dynamic extraction method from the original MVP code
        workplace_type, job_type, job_budget = self._extract_topcard_job_details(page)
        
        if workplace_type:
            self.job_details["Workplace Type"] = workplace_type
            
        if job_type:
            self.job_details["Job Type"] = job_type
            
        if job_budget and self._validate_salary(job_budget):
            self.job_details["Job Budget"] = job_budget
                
    def _extract_topcard_job_details(self, page: Page) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Dynamically locate the Job Top Card container,
        and extract Workplace Type, Job Type, and Job Budget (Salary) from inside it.
        No class name dependencies. Processes all buttons inside container.
        """
        workplace_type = None
        job_type = None
        job_budget = None

        try:
            # Step 1: Dynamically find the correct top-card container
            top_card_container = None
            divs = page.locator("div")
            div_count = divs.count()

            for i in range(div_count):
                div = divs.nth(i)

                try:
                    # Early skip if div is invisible or too small
                    bounding_box = div.bounding_box(timeout=2000)
                    if not bounding_box or bounding_box["height"] < 50 or bounding_box["width"] < 100:
                        continue
                        
                    if not div.is_visible(timeout=2000):
                        continue
                        
                    has_title = div.locator("h1, h2, h3").count() > 0
                    has_buttons = div.locator("button").count() > 0

                    if has_title and has_buttons:
                        top_card_container = div
                        logger.debug(f"Top card container found at div #{i}")
                        break

                except Exception as e:
                    logger.debug(f"Div #{i} skipped due to error: {e}")

            if not top_card_container:
                logger.warning("Top card container not found dynamically.")
                return workplace_type, job_type, job_budget

            # Step 2: Extract all buttons inside the top card container
            buttons = top_card_container.locator("button")
            button_count = buttons.count()

            for i in range(button_count):
                try:
                    button = buttons.nth(i)

                    button_text = ""

                    spans = button.locator("span")
                    span_count = spans.count()

                    if span_count > 0:
                        parts = []
                        for j in range(span_count):
                            try:
                                part = spans.nth(j).inner_text(timeout=2000).strip()
                                if part:
                                    parts.append(part)
                            except Exception as e:
                                logger.debug(f"Span #{j} inside button unreadable: {e}")
                        
                        button_text = " ".join(parts).strip().lower()

                    else:
                        try:
                            button_text = button.inner_text(timeout=3000).strip().lower()
                        except Exception as e:
                            logger.debug(f"Button #{i} unreadable directly: {e}")
                            button_text = ""

                    logger.debug(f"Button {i} full text: {button_text}")

                    # Match Job Budget (salary)
                    if not job_budget: 
                        # Check for currency symbols in the text
                        if any(symbol in button_text for symbol in ["₹", "$", "€", "£"]):
                            job_budget_text = button.inner_text(timeout=3000).strip()
                            
                            # Skip if contains "premium" or suspicious content
                            if any(term in job_budget_text.lower() for term in self.SUSPICIOUS_TERMS):
                                logger.debug(f"Skipping likely non-salary text: '{job_budget_text}'")
                                continue
                                
                            # Log the raw text for debugging
                            logger.debug(f"Found potential salary text: '{job_budget_text}'")
                            
                            # For Indian Rupee format like "₹2.5M/yr - ₹2.7M/yr"
                            rupee_match = re.search(r"(₹[\d,.]+[KlMB]?(?:/yr|/hr|/day|/month)?)(?:\s*-\s*(₹[\d,.]+[KlMB]?(?:/yr|/hr|/day|/month)?))?", job_budget_text)
                            if rupee_match:
                                job_budget = rupee_match.group(0)
                                # Verify it looks like a salary (has digits)
                                if re.search(r"\d", job_budget):
                                    logger.debug(f"Indian Rupee salary detected: {job_budget}")
                                else:
                                    job_budget = None
                            
                            # For dollar format like "$50K/yr - $70K/yr"
                            dollar_match = re.search(r"(\$[\d,]+(?:K|M)?(?:/yr|/hr|/day|/month)?)(?:\s*-\s*(\$[\d,]+(?:K|M)?(?:/yr|/hr|/day|/month)?))?", job_budget_text)
                            if dollar_match and not job_budget:
                                job_budget = dollar_match.group(0)
                                # Verify it looks like a salary (has digits)
                                if re.search(r"\d", job_budget):
                                    logger.debug(f"Dollar salary detected: {job_budget}")
                                else:
                                    job_budget = None
                                
                            # General currency capture if specific formats fail
                            if not job_budget:
                                # Try to match any currency with number
                                currency_match = re.search(r"[₹$€£][\d,.]+(K|M|B)?(/\w+)?(\s*-\s*[₹$€£][\d,.]+(K|M|B)?(/\w+)?)?", job_budget_text)
                                if currency_match:
                                    job_budget = currency_match.group(0)
                                    # Verify it looks like a salary (has digits)
                                    if re.search(r"\d", job_budget):
                                        logger.debug(f"Generic currency match: {job_budget}")
                                    else:
                                        job_budget = None

                    # Match Workplace Type
                    if not workplace_type:
                        if "on-site" in button_text or "onsite" in button_text:
                            workplace_type = "On-site"
                        elif "remote" in button_text:
                            workplace_type = "Remote"
                        elif "hybrid" in button_text:
                            workplace_type = "Hybrid"

                    # Match Job Type using regex
                    if not job_type:
                        if re.search(r"\bfull[\s-]?time\b", button_text):
                            job_type = "Full-time"
                        elif re.search(r"\bpart[\s-]?time\b", button_text):
                            job_type = "Part-time"
                        elif "contract" in button_text:
                            job_type = "Contract"
                        elif "internship" in button_text:
                            job_type = "Internship"
                        elif "temporary" in button_text:
                            job_type = "Temporary"
                        elif "volunteer" in button_text:
                            job_type = "Volunteer"
                        elif "other" in button_text:
                            job_type = "Other"

                    # Early exit if workplace and job type found
                    if workplace_type and job_type and job_budget:
                        logger.debug(f"Found all job details. Early exit.")
                        break

                except Exception as e:
                    logger.debug(f"Skipped unreadable button #{i}: {e}")
            
            # Look for salary in dedicated compensation section
            if not job_budget:
                try:
                    # Look for the section with compensation
                    compensation_section = page.locator("section:has-text('Compensation'), div.jobs-unified-compensation__container")
                    
                    if compensation_section.is_visible(timeout=1000):
                        comp_text = compensation_section.inner_text(timeout=3000)
                        
                        # Skip if contains "premium" or other suspicious content
                        if any(term in comp_text.lower() for term in self.SUSPICIOUS_TERMS):
                            logger.debug(f"Skipping likely non-salary section text: '{comp_text}'")
                        else:
                            logger.debug(f"Found compensation section: '{comp_text}'")
                            
                            # Apply same regex patterns to capture salary information
                            rupee_match = re.search(r"(₹[\d,.]+[KlMB]?(?:/yr|/hr|/day|/month)?)(?:\s*-\s*(₹[\d,.]+[KlMB]?(?:/yr|/hr|/day|/month)?))?", comp_text)
                            if rupee_match:
                                salary_text = rupee_match.group(0)
                                # Verify it looks like a salary (has digits)
                                if re.search(r"\d", salary_text):
                                    job_budget = salary_text
                                    logger.debug(f"Indian Rupee salary detected from compensation section: {job_budget}")
                            
                            # If no rupee match, try dollar match
                            if not job_budget:
                                dollar_match = re.search(r"(\$[\d,]+(?:K|M)?(?:/yr|/hr|/day|/month)?)(?:\s*-\s*(\$[\d,]+(?:K|M)?(?:/yr|/hr|/day|/month)?))?", comp_text)
                                if dollar_match:
                                    salary_text = dollar_match.group(0)
                                    # Verify it looks like a salary (has digits)
                                    if re.search(r"\d", salary_text):
                                        job_budget = salary_text
                                        logger.debug(f"Dollar salary detected from compensation section: {job_budget}")
                except Exception as e:
                    logger.debug(f"Error looking for compensation section: {e}")

        except Exception as e:
            logger.warning(f"Top card extraction failed: {e}")

        return workplace_type, job_type, job_budget
                
    def _extract_urls_and_company(self, page: Page) -> None:
        """Extract company and hiring manager URLs."""
        # Job URL - using original logic from MVP
        try:
            job_url = page.locator("h1.t-24 a").first.get_attribute("href")
            if job_url: 
                job_url = job_url.split("?")[0]
                if not job_url.startswith("https://"):
                    job_url = "https://www.linkedin.com" + job_url
                self.job_details["Job URL"] = job_url
        except:
            # Fallback to current page URL if the above method fails
            self.job_details["Job URL"] = page.url.split("?")[0]
                
        # Company LinkedIn URL    
        try:
            company_link_elem = page.locator("div.job-details-jobs-unified-top-card__company-name")
            company_url = self._extract_href(company_link_elem, "a")
            if company_url:
                    self.job_details["Company LinkedIn URL"] = company_url
        except Exception as e:
            logger.debug(f"Error extracting company URL: {e}")
            
        # Hiring Manager - using original logic from MVP
        try:
            hirer_card = page.locator("div.hirer-card__hirer-information")
            hiring_manager_url = self._extract_href(hirer_card, "a")
            if hiring_manager_url:
                self.job_details["Hiring Manager URL"] = hiring_manager_url
        except Exception as e:
            logger.debug(f"Error extracting Hiring Manager URL: {e}")
                
    def _extract_industry_and_employees(self, page: Page) -> None:
        """Extract industry and company employee information using original logic."""
        # Sector / Industry - using original logic from MVP
        try:
            industry_text = page.locator('div.t-14.mt5').first.text_content().strip()
            lines = [line.strip() for line in industry_text.split('\n') if line.strip()]
            self.job_details["Industry"] = lines[0] if lines else ""
        except:
            pass
            
        # Total Employees - using original logic from MVP
        try:
            employees_text = page.locator("section[data-view-name='job-details-about-company-module'] span.jobs-company__inline-information").first.text_content().strip()
            employee_range = employees_text.replace("employees", "").strip()
            
            if employee_range:
                employee_range = str(employee_range).strip()

            self.job_details["Total Employees"] = f'="{employee_range}"'
        except:
            self.job_details["Total Employees"] = ""
            
    def _extract_href(self, locator: Locator, selector: str, default: str = "") -> str:
        """Extract href attribute from a locator + selector combination."""
        try:
            href = locator.locator(selector).get_attribute("href", timeout=SHORT_WAIT)
            if href:
                return href if href.startswith("http") else "https://www.linkedin.com" + href
            return default
        except:
            return default
    
    def _extract_salary(self, text: str) -> Optional[str]:
        """Extract salary information from text."""
        if not text:
            return None
            
        # Skip suspicious content
        if any(term in text.lower() for term in self.SUSPICIOUS_TERMS):
            return None
            
        # Try rupee pattern
        rupee_match = re.search(self.RUPEE_PATTERN, text)
        if rupee_match:
            return rupee_match.group(0)
            
        # Try dollar pattern
        dollar_match = re.search(self.DOLLAR_PATTERN, text)
        if dollar_match:
            return dollar_match.group(0)
            
        # Try generic currency pattern
        currency_match = re.search(self.GENERIC_CURRENCY, text)
        if currency_match:
            return currency_match.group(0)
            
        return None
        
    def _extract_from_compensation(self, page: Page) -> Optional[str]:
        """Extract salary from dedicated compensation section."""
        compensation = self._get_from_selectors(page, self.SELECTORS["compensation_section"])
        if compensation:
            return self._extract_salary(compensation)
        return None
        
    def _validate_salary(self, salary: str) -> bool:
        """Validate if a salary string is legitimate."""
        if not salary:
            return False
            
        # Must contain digits
        if not re.search(r'\d', salary):
            return False
            
        # Check for suspicious terms
        if any(term in salary.lower() for term in self.SUSPICIOUS_TERMS):
            return False
            
        # Check for zero values
        zero_patterns = [r'[\$₹€£]\s*0', r'[\$₹€£]\s*0[./,]0']
        if any(re.search(pattern, salary) for pattern in zero_patterns):
            return False
            
        return True 