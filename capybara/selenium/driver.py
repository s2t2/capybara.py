import atexit
from contextlib import contextmanager
from selenium import webdriver
from selenium.common.exceptions import NoAlertPresentException, UnexpectedAlertPresentException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from time import sleep, time

import capybara
from capybara.driver.base import Base
from capybara.exceptions import ModalNotFound
from capybara.selenium.node import Node
from capybara.utils import cached_property


class Driver(Base):
    def __init__(self, app):
        self.app = app
        self._frame_handles = []

    @cached_property
    def browser(self):
        browser = webdriver.Firefox(
            # Auto-accept unload alerts triggered by navigating away.
            capabilities={"unexpectedAlertBehaviour": "ignore"})
        atexit.register(browser.quit)
        return browser

    @property
    def title(self):
        return self.browser.title

    @property
    def html(self):
        return self.browser.page_source

    @property
    def text(self):
        return self.browser.text

    def switch_to_frame(self, frame):
        if frame == "parent":
            self._frame_handles.pop()
            self.browser.switch_to.default_content()
            for frame_handle in self._frame_handles:
                self.browser.switch_to.frame(frame_handle)
        else:
            self._frame_handles.append(frame.native)
            self.browser.switch_to.frame(frame.native)

    def visit(self, url):
        self.browser.get(url)

    def execute_script(self, script):
        self.browser.execute_script(script)

    def evaluate_script(self, script):
        return self.browser.execute_script("return {0}".format(script))

    @contextmanager
    def accept_modal(self, modal_type, text=None, response=None, wait=None):
        yield
        modal = self._find_modal(text=text, wait=wait)
        if response:
            modal.send_keys(response)
        modal.accept()

    @contextmanager
    def dismiss_modal(self, modal_type, text=None, wait=None):
        yield
        modal = self._find_modal(text=text, wait=wait)
        modal.dismiss()

    def reset(self):
        # Avoid starting the browser just to reset the session.
        if "browser" in self.__dict__:
            navigated = False
            start_time = time()
            while True:
                try:
                    # Only trigger a navigation if we haven't done it already,
                    # otherwise it can trigger an endless series of unload modals.
                    if not navigated:
                        self.browser.get("about:blank")
                        navigated = True

                    break
                except UnexpectedAlertPresentException:
                    # This error is thrown if an unhandled alert is on the page.
                    try:
                        self.browser.switch_to.alert.accept()

                        # Allow time for the modal to be handled.
                        sleep(0.25)
                    except NoAlertPresentException:
                        # The alert is now gone. Nothing to do.
                        pass

                    # Try cleaning up the browser again.
                    continue

    def _find_css(self, css):
        return [Node(self, element) for element in self.browser.find_elements_by_css_selector(css)]

    def _find_xpath(self, xpath):
        return [Node(self, element) for element in self.browser.find_elements_by_xpath(xpath)]

    def _find_modal(self, text=None, wait=None):
        wait = wait or capybara.default_max_wait_time
        WebDriverWait(self.browser, wait).until(EC.alert_is_present())
        alert = self.browser.switch_to.alert
        if alert is None:
            raise ModalNotFound("Unable to find modal dialog")
        if text and text not in alert.text:
            raise ModalNotFound("Unable to find modal dialog with {0}".format(text))
        return alert
