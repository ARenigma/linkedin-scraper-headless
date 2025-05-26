import time
from typing import Tuple, Optional
from playwright.sync_api import Page, BrowserContext, Browser, Playwright

from config import (
    logger, DEFAULT_TIMEOUT, MAX_RETRIES,
    BROWSER_OPTIONS, USER_AGENT
)

class BrowserManager:
    """Handles browser session management and recovery for headless mode."""
    
    def __init__(self, playwright: Playwright):
        self.playwright = playwright
        self.browser = None
        self.context = None
        self.page = None
        
    def connect(self) -> Tuple[Page, BrowserContext, Browser]:
        """Launch a headless browser and establish connection."""
        return self.launch_headless_browser()
    
    def launch_headless_browser(self) -> Tuple[Page, BrowserContext, Browser]:
        """Launch a new headless browser instance."""
        try:
            # Launch new browser with anti-detection options
            self.browser = self.playwright.chromium.launch(**BROWSER_OPTIONS)
            
            # Create a context with custom user agent
            self.context = self.browser.new_context(
                user_agent=USER_AGENT
            )
            
            # Setup browser evasion
            self._set_evasions(self.context)
            
            self.page = self.context.new_page()
            logger.info("Headless browser launched successfully")
            return self.page, self.context, self.browser
        except Exception as e:
            logger.error(f"Headless browser launch failed: {e}")
            raise
            
    def ensure_alive(self, login_callback, combo_counter=None, revalidate_every=5) -> Tuple[Page, BrowserContext, Browser]:
        """
        Ensure browser, context and page are alive.
        Implements a hierarchical recovery system.
        """
        # Check if browser is connected
        try:
            if getattr(self.browser, "is_closed", lambda: True)():
                logger.info("Browser connection lost, reconnecting")
                return self.reconnect_browser(login_callback)
        except Exception:
            logger.warning("Error checking browser connection")
            
        # Check if page is closed
        try:
            page_is_closed = self.page.is_closed()
        except Exception:
            page_is_closed = True
            
        # Check if context is valid
        try:
            context_is_valid = not getattr(self.context, "is_closed", lambda: True)()
            if not page_is_closed and context_is_valid:
                _ = self.context.pages  # Test operation
            else:
                context_is_valid = False
        except Exception:
            context_is_valid = False
            
        # Recovery logic
        if page_is_closed and context_is_valid:
            logger.info("Page was closed, creating new page")
            try:
                self.page = self.context.new_page()
            except Exception:
                context_is_valid = False
                
        if not context_is_valid:
            logger.info("Context invalid, creating new context")
            try:
                self._clean_close(self.context)
                self.context = self.browser.new_context(user_agent=USER_AGENT)
                self._set_evasions(self.context)
                self.page = self.context.new_page()
            except Exception:
                logger.warning("Context creation failed, resetting browser")
                return self.reconnect_browser(login_callback)
                
        # Revalidate login if needed
        if combo_counter is not None and combo_counter % revalidate_every == 0:
            logger.info(f"Session checkpoint at combo #{combo_counter}")
            try:
                self.page, self.context = login_callback(self.page, self.context, self.browser)
            except Exception as e:
                logger.error(f"Login revalidation failed: {e}")
                return self.reconnect_browser(login_callback)
                
        return self.page, self.context, self.browser
        
    def reconnect_browser(self, login_callback) -> Tuple[Page, BrowserContext, Browser]:
        """Complete browser reconnection with login for headless mode."""
        try:
            self._clean_close(self.browser)
            
            # Launch a new headless browser
            self.browser = self.playwright.chromium.launch(**BROWSER_OPTIONS)
            self.context = self.browser.new_context(user_agent=USER_AGENT)
            self._set_evasions(self.context)
            self.page = self.context.new_page()
            logger.info("Headless browser relaunched")
            
            # Perform login
            self.page, self.context = login_callback(self.page, self.context, self.browser)
            return self.page, self.context, self.browser
        except Exception as e:
            logger.critical(f"Complete browser reconnection failed: {e}")
            raise
    
    def _set_evasions(self, context):
        """Setup evasions to avoid bot detection."""
        try:
            context.add_init_script("""() => {
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
            
    def _clean_close(self, resource):
        """Safely close a browser resource."""
        if resource:
            try:
                resource.close()
            except Exception:
                pass  # Ignore errors on close 