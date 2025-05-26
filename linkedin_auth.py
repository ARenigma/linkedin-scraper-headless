import os
import time
from typing import Tuple
from datetime import datetime
from playwright.sync_api import Page, BrowserContext
from config import (
    logger, USERNAME, PASSWORD, SCREENSHOT_FOLDER, 
    DEFAULT_TIMEOUT, DEFAULT_WAIT, SHORT_WAIT,
    USER_AGENT
)

class LinkedInAuth:
    """Handles LinkedIn authentication and session management."""
    
    # Login detection
    FEED_INDICATORS = [
        ".global-nav__me-photo",  # Profile photo
        ".feed-identity-module",   # Feed identity module
        ".feed-shared-update-v2",  # Feed posts
        ".share-box-feed-entry"    # Post creation box
    ]
    
    LOGIN_INDICATORS = [
        "Sign in", "Forgot password", "Welcome back", 
        "Email or Phone", "Password"
    ]
    
    SECURITY_CHALLENGE_INDICATORS = [
        "checkpoint", "challenge", "unusual", "verify", "captcha", "security"
    ]
    
    def __init__(self, username=None, password=None):
        self.username = username or USERNAME
        self.password = password or PASSWORD
        
        if not self.username or not self.password:
            raise ValueError("LinkedIn credentials missing. Set LINKEDIN_USERNAME and LINKEDIN_PASSWORD env vars.")
        
        # Ensure screenshot folder exists
        os.makedirs(SCREENSHOT_FOLDER, exist_ok=True)
    
    def login(self, page: Page, context: BrowserContext, browser) -> Tuple[Page, BrowserContext]:
        """Main authentication flow."""
        logger.info("Checking LinkedIn login status")
        max_attempts = 3
        
        for attempt in range(max_attempts):
            try:
                logger.info(f"LinkedIn login attempt {attempt+1}/{max_attempts}")
                
                # Go directly to login page for more reliability in headless mode
                page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT)
                page.wait_for_timeout(DEFAULT_WAIT)
                
                # Set evasions
                self._set_evasions(page)
                
                # Take screenshot for debugging
                self._take_screenshot(page, f"login_before_{attempt+1}")
                
                # Check if already logged in by looking at URL
                if "linkedin.com/feed" in page.url:
                    logger.info("Already on feed URL, checking login status...")
                    # Give elements time to load if we're already on feed page
                    page.wait_for_timeout(3000)
                    if self._check_logged_in(page):
                        logger.info("✅ Already logged in to LinkedIn!")
                        return page, context
                    else:
                        logger.info("On feed URL but not fully logged in yet, waiting...")
                        # Wait a bit longer for elements to load 
                        page.wait_for_timeout(5000)
                        if self._check_logged_in(page):
                            logger.info("✅ Successfully logged in to LinkedIn after waiting!")
                            return page, context
                
                # If on login page, perform login
                if self._is_on_login_page(page):
                    logger.info("🔑 Login form detected, filling credentials...")
                    self._perform_login(page)
                    
                    # Take screenshot after login attempt
                    self._take_screenshot(page, f"login_after_{attempt+1}")
                    
                    # Check for security challenges
                    if self._is_security_challenge(page):
                        error_msg = "LinkedIn security challenge detected!"
                        logger.error(f"🚨 {error_msg} Cannot proceed in headless mode.")
                        self._take_screenshot(page, "security_challenge")
                        raise Exception(f"{error_msg} Try running in headed mode.")
                    
                    # Check if we've been redirected to feed URL, even if elements aren't loaded yet
                    if "linkedin.com/feed" in page.url:
                        logger.info("Redirected to feed URL after login, waiting for elements...")
                        # Extended wait for feed elements to load
                        page.wait_for_timeout(5000)
                    
                    # Check if login successful
                    if self._check_logged_in(page):
                        logger.info("✅ Successfully logged in to LinkedIn!")
                        return page, context
                    
                    # One more check with feed URL (URL might be correct but elements not loaded)
                    if "linkedin.com/feed" in page.url:
                        logger.info("On feed URL but login check failed, trying again after a longer wait...")
                        page.wait_for_timeout(8000)  # Extended wait
                        if self._check_logged_in(page):
                            logger.info("✅ Successfully logged in to LinkedIn after extended wait!")
                            return page, context
                        else:
                            logger.warning(f"⚠️ On feed URL but login elements not detected after extended wait")
                    else:
                        logger.warning(f"⚠️ Login attempt {attempt+1} failed, current URL: {page.url}")
                else:
                    # If not on login page but also not logged in, try direct navigation to feed
                    logger.info("Not on login page, trying to navigate to feed")
                    page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT)
                    
                    # Extended wait for feed to load
                    page.wait_for_timeout(5000)
                    
                    if self._check_logged_in(page):
                        logger.info("✅ Successfully logged in to LinkedIn!")
                        return page, context
            
                # Wait before retry
                page.wait_for_timeout(3000)
                
            except Exception as e:
                logger.error(f"❌ Login error on attempt {attempt+1}: {e}")
                
                # Try with a new context for the next attempt
                if attempt < max_attempts - 1:
                    try:
                        context.close()
                    except:
                        pass
                        
                    context = browser.new_context(user_agent=USER_AGENT)
                    page = context.new_page()
                    self._set_evasions(page)
        
        # If all attempts failed
        logger.error("❌ All login attempts failed! Could not log in to LinkedIn.")
        raise Exception("Failed to log in to LinkedIn after multiple attempts")
            
    def _check_logged_in(self, page: Page) -> bool:
        """Check if user is logged in by looking for feed indicators."""
        # Check URL first - most reliable indicator
        try:
            if "linkedin.com/feed" in page.url:
                logger.info("Feed URL detected")
                
                # Check for essential elements that indicate logged-in state
                essential_selectors = [
                    ".global-nav__me-photo",        # Profile photo (most reliable)
                    "nav.global-nav",               # Global navigation bar
                    ".feed-identity-module",        # Feed identity module
                    "[data-control-name='identity_welcome_message']", # Welcome message
                    ".search-global-typeahead__input" # Search box
                ]
                
                # Try several selectors, return true if any are visible
                for selector in essential_selectors:
                    try:
                        if page.locator(selector).is_visible(timeout=SHORT_WAIT):
                            logger.info(f"Detected logged in state via {selector}")
                            return True
                    except:
                        continue
                        
                # If none of the above are visible, check page content
                try:
                    page_text = page.inner_text("body", timeout=SHORT_WAIT).lower()
                    feed_keywords = [
                        "my network", "jobs", "messaging", "notifications", 
                        "profile", "post", "share", "your feed"
                    ]
                    
                    matching_keywords = [kw for kw in feed_keywords if kw in page_text]
                    if matching_keywords:
                        logger.info(f"Detected logged in state via text: {', '.join(matching_keywords)}")
                        return True
                except:
                    pass
                    
                # As a last resort, check if there's a logout button
                try:
                    # Check if we can find the sign out option in the menu
                    if page.locator("button:has-text('Sign out'), a:has-text('Sign out')").count() > 0:
                        logger.info("Detected logged in state via sign out button existence")
                        return True
                except:
                    pass
        except Exception as e:
            logger.debug(f"Error checking login status via URL: {e}")
        
        # If we're not on feed URL, do additional checks
        try:
            # Check for profile photo - reliable indicator
            if page.locator(".global-nav__me-photo").is_visible(timeout=SHORT_WAIT):
                logger.info("Detected logged in state via profile photo")
                return True
                
            # Check for global navigation
            if page.locator("nav.global-nav").is_visible(timeout=SHORT_WAIT):
                logger.info("Detected logged in state via navigation menu")
                return True
                
            # Check if we're on any LinkedIn page with profile elements
            current_url = page.url
            if "linkedin.com" in current_url and "login" not in current_url and "signup" not in current_url:
                # Try to check if there are profile elements
                try:
                    profile_indicators = [
                        ".profile-rail-card",
                        ".identity-headline",
                        ".pv-top-card"
                    ]
                    
                    for indicator in profile_indicators:
                        if page.locator(indicator).count() > 0:
                            logger.info(f"Detected logged in state via profile element: {indicator}")
                            return True
                except:
                    pass
                    
                # Look for header or menu elements that only appear when logged in
                header_indicators = [
                    "header.global-nav__responsive-header",
                    ".global-nav__primary-items"
                ]
                
                for indicator in header_indicators:
                    if page.locator(indicator).count() > 0:
                        logger.info(f"Detected logged in state via header element: {indicator}")
                        return True
        except Exception as e:
            logger.debug(f"Error in secondary login checks: {e}")
            
        return False
    
    def _is_on_login_page(self, page: Page) -> bool:
        """Check if current page is the login page."""
        try:
            # Check URL first
            if "linkedin.com/login" in page.url or "checkpoint" in page.url:
                return True
                
            # Check for login form elements
            username_field = page.locator("input#username, input[name='session_key']")
            password_field = page.locator("input#password, input[name='session_password']")
            
            if username_field.is_visible(timeout=SHORT_WAIT) and password_field.is_visible(timeout=SHORT_WAIT):
                return True
                
            # Check page text for login indicators
            page_text = page.inner_text("body", timeout=SHORT_WAIT).lower()
            return any(indicator.lower() in page_text for indicator in self.LOGIN_INDICATORS)
        except Exception as e:
            logger.debug(f"Error checking if on login page: {e}")
            return False
    
    def _is_security_challenge(self, page: Page) -> bool:
        """Check if LinkedIn is showing a security challenge."""
        try:
            # Check URL for challenge indicators
            current_url = page.url.lower()
            if any(indicator in current_url for indicator in ["checkpoint", "challenge"]):
                return True
                
            # Check page content for security challenge text
            page_text = page.inner_text("body", timeout=SHORT_WAIT).lower()
            security_phrases = [
                "unusual login", "verify it's you", "security verification",
                "verify your identity", "confirm your identity", "recognize your device",
                "unusual activity", "captcha", "complete a security check"
            ]
            
            if any(phrase in page_text for phrase in security_phrases):
                return True
                
            # Check for specific security challenge elements
            challenge_selectors = [
                "input#captcha-internal", 
                ".challenge-dialog",
                "form.two-step-challenge"
            ]
            
            for selector in challenge_selectors:
                if page.locator(selector).count() > 0:
                    return True
                    
            return False
            
        except Exception as e:
            logger.debug(f"Error checking for security challenge: {e}")
            return False
    
    def _perform_login(self, page: Page) -> None:
        """Fill login form and submit."""
        try:
            # Find username field with multiple selectors
            username_selectors = ["#username", "input[name='session_key']", "input[autocomplete='username']"]
            username_field = None
            
            for selector in username_selectors:
                try:
                    if page.locator(selector).is_visible(timeout=SHORT_WAIT):
                        username_field = page.locator(selector)
                        break
                except:
                    continue
            
            # Find password field with multiple selectors
            password_selectors = ["#password", "input[name='session_password']", "input[type='password']"]
            password_field = None
            
            for selector in password_selectors:
                try:
                    if page.locator(selector).is_visible(timeout=SHORT_WAIT):
                        password_field = page.locator(selector)
                        break
                except:
                    continue
            
            if not username_field or not password_field:
                logger.warning("Could not find username or password fields")
                return
                
            # Clear fields first to avoid issues with autofill
            username_field.fill("")
            password_field.fill("")
            
            # Type credentials with small delay to seem more human-like
            username_field.type(self.username, delay=100)
            page.wait_for_timeout(1000)
            password_field.type(self.password, delay=100)
            
            # Click sign-in button
            signin_button = page.locator("button[type='submit']")
            if signin_button.is_visible(timeout=SHORT_WAIT):
                logger.info("Clicking sign-in button...")
                signin_button.click()
                
                # Instead of waiting for navigation, wait for a fixed time
                # and then check if we're on the feed page
                logger.info("Waiting for login to complete...")
                page.wait_for_timeout(5000)  # Wait 5 seconds
                
                # Check if URL indicates we've been redirected to feed
                if "linkedin.com/feed" in page.url:
                    logger.info(f"After login, URL is now: {page.url}")
                    # Additional wait for feed elements to load
                    page.wait_for_timeout(2000)
                    return
                
                # If not on feed yet, wait a bit longer
                if not "linkedin.com/feed" in page.url:
                    logger.info("Not on feed yet, waiting longer...")
                    page.wait_for_timeout(5000)  # Wait another 5 seconds
            else:
                logger.warning("Sign-in button not found")
                
        except Exception as e:
            logger.warning(f"Login attempt error: {e}")
    
    def _take_screenshot(self, page: Page, name: str) -> None:
        """Take a screenshot for debugging purposes."""
        try:
            screenshot_path = os.path.join(SCREENSHOT_FOLDER, f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            page.screenshot(path=screenshot_path)
            logger.debug(f"Screenshot saved to {screenshot_path}")
        except Exception as e:
            logger.warning(f"Failed to take screenshot: {e}")
    
    def _set_evasions(self, page: Page) -> None:
        """Setup evasions to avoid bot detection."""
        try:
            # Set navigator properties to avoid detection
            page.evaluate("""() => {
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => false
                });
                
                // Override permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
                
                // Pass various bot detection tests
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
            }""")
        except Exception as e:
            logger.debug(f"Failed to set evasions: {e}")
            
    def _try_with_fresh_context(self, browser) -> Tuple[Page, BrowserContext]:
        """Create a fresh context and attempt login again."""
        logger.info("Trying with fresh context")
        try:
            context = browser.new_context(user_agent=USER_AGENT)
            page = context.new_page()
            self._set_evasions(page)
            
            # Go directly to login page
            page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT)
            
            # If already on feed page
            if "linkedin.com/feed" in page.url and self._check_logged_in(page):
                return page, context
                
            # Try login if needed
            if self._is_on_login_page(page):
                self._perform_login(page)
                
                # Check login result
                if self._check_logged_in(page):
                    return page, context
            
            # If we reach here, all login attempts failed
            logger.error("All login attempts failed")
            raise Exception("Failed to log in to LinkedIn after multiple attempts")
            
        except Exception as e:
            logger.error(f"Fresh context login failed: {e}")
            raise 