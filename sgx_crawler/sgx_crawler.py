import re
import json
import logging
from .utils import load_config, write_config, get, write
from datetime import datetime


class sgx_crawler:

    def __init__(self, config_path: str, logger: logging.Logger) -> None:
        """A crawler to download SGX data

        :param config_path: the path of the configuration file
        :param logger: the Logger
        """

        self.config_path = config_path
        self.config = load_config(config_path, logger)

        try:
            self.get_trade_date = self.config["get-trade-date"]
            self.get_download = self.config["get-download"]
            self.headers_pool = self.config["headers-pool"]
            self.file_folder = list(self.config["file-folder"].items())
            self.index = self.config[
                "start-from"] if self.config["start-from"] > 31 else 31
            self.pendings = list()  # failed tasks waiting for retrying
            self.datestr = ""
            self.logger = logger
        except KeyError as e:
            self.logger.exception(e, exc_info=False)
            exit()

    def retry(self) -> None:
        """Retry the failed tasks"""

        self.logger.info("Resume pending tasks")

        retry_tasks, self.pendings = self.pendings, list()

        while retry_tasks:
            args = retry_tasks.pop(0)
            self.download_single(*args, replace=True)

    def download_history(self, replace: bool = False) -> None:
        """Download all history files start from self.index

        :param replace: replace the existing files with new downloads, default False
        """

        if self.pendings:  # retry first
            self.retry()

        indicator = -1
        while indicator != 2:
            # stop when having too many failed tasks
            if len(self.pendings) > 20:
                self.logger.critical(
                    "Over 20 tasks failed -- Check Internet Connection")
                self.index += 1
                break
            # download 4 files
            for i in range(4):
                indicator = self.download_single(self.index, i, replace)
                # no record found --> all history files are retrieved
                if indicator == 2:
                    break
            self.index += 1

        self.index -= 1
        self.logger.debug("Stop update")

        # save the index of the first failed task to config
        if self.pendings:
            self.logger.warning("There exist failed tasks")
            self.config["start-from"] = self.pendings[0][0]
            write_config(self.config_path, self.config, self.logger)
        else:
            self.logger.info("All Success")

    def download_single(self,
                        index: int,
                        file_id: int,
                        replace: bool = False) -> int:
        """Download a single file on specified date

        :param index: the index of the trade date
        :param file_id: the file to download:
            0: WEBPXTICK_DT-*.zip
            1: TickData_structure.dat
            2: TC_*.txt
            3: TC_structure.dat
        :param replace: replace the existing files with new downloads, default False
        :return: the status indicator:
            0: wrong parameter
            1: download/write failed; auto-retry
            2: no record found --> all history files are retrieved
            3: success
        """

        # check file_id
        if file_id < 0 or file_id > 3:
            self.logger.warning("file_id out of range [0, 3]")
            return 0

        # check index
        if index < 31:
            self.logger.warning("index out of range [31, ]")
            return 0

        # config the download link
        kwargs = self.get_download.copy()
        kwargs["url"] += str(index) + self.file_folder[file_id][0]

        # get the file
        r = get(kwargs, self.headers_pool, self.logger)

        # failed to get the file, add this task to pendings
        if r is None:
            self.pendings.append([index, file_id])
            self.logger.error(
                "Fail to download/write: index %d, file_id %d; retry later" %
                (index, file_id))
            return 1

        # index of out range
        if r.headers["Content-Type"] == "text/html; charset=utf-8":
            self.logger.debug("All history files are retrieved!")
            return 2

        # the right file
        elif r.headers["Content-Type"] == "application/download":
            # extract the filename
            filename = re.findall(r"[\S]+\s[a-z]+=([\S]+)",
                                  r.headers["Content-Disposition"])[0]

            # extract date from WEBPXTICK_DT-*.zip
            if file_id == 0:
                self.datestr = re.findall(r"[A-Z]+(-[0-9]+\.).+", filename)[0]
            # add date the filename of *_structure.dat
            elif file_id & 1:
                temp = filename.split(".")
                filename = temp[0] + self.datestr + temp[1]

            # failed to write the file, add this task to pendings
            if not write(self.file_folder[file_id][1], filename, r,
                         self.logger, replace):
                self.logger.error(
                    "Fail to download/write: index %d, file_id %d; retry later"
                    % (index, file_id))
                self.pendings.append([index, file_id])
                return 1
            # success
            return 3

    def is_trade_date(self, check_date: datetime) -> bool:
        """Check whether the given date is a trade date

        :param check_date: a date
        :return: True if it's a valid trade date else False
        """

        # get recent 10 trade dates
        r = get(self.get_trade_date, self.headers_pool, self.logger)

        # failed to check the trade date
        if r is None:
            self.logger.error("Fail to check trade date")
            return False

        try:
            data = json.loads(r.content.decode())['data']
            last_trade_date = data[-1]["base-date"]
        except KeyError as e:
            self.logger.exception(e, exc_info=False)
            exit()

        return last_trade_date == datetime.strftime(check_date, "%Y%m%d")
