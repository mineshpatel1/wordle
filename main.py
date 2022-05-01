import time
from utils import log
from web_drivers.nyt_web_driver import NYTWebDriver
from web_drivers.quordle_web_driver import QuordleWebDriver


if __name__ == '__main__':
    QuordleWebDriver().play()
