import os
import re
import json
import logging
import logging.config
from .utils import load_config, write_config, get, write, date_to_index
from datetime import datetime

local_crawler_config = os.path.join(os.path.dirname(__file__),
                                    'crawlerconfig.json')
local_log_config = os.path.join(os.path.dirname(__file__), 'logconfig.json')


class sgx_crawler:

    def __init__(self,
                 config_path: str = None,
                 logger: logging.Logger = None) -> None:
        """A crawler to download SGX data

        :param config_path: the path of the configuration file; if None then use default
        :param logger: the Logger; if None then use default
        """

        try:
            if logger is None:  # default logger
                logconfig = load_config(local_log_config)
                logging.config.dictConfig(logconfig)
                logger = logging.getLogger("sgx_crawler_default")
                logger.info("Use default logger")

            self.logger = logger

            if config_path is None:
                config_path = local_crawler_config
                self.logger.info("Use default configuration")

            self.config_path = config_path
            self.config = load_config(self.config_path, logger)
            self.get_trade_date = self.config["get-trade-date"]
            self.get_download = self.config["get-download"]
            self.headers_pool = self.config["headers-pool"]
            self.file_folder = list(self.config["file-folder"].items())
            self.index = max(
                (self.config["resume-from"], self.config["start-from"], 31))

            self.pendings = list()  # failed tasks waiting for retrying
            self.datestr = ""
        except Exception as e:
            self.logger.exception(e, exc_info=False)
            exit()

    def retry(self) -> None:
        """Retry the failed tasks"""

        self.logger.info("Resume pending tasks")

        retry_tasks, self.pendings = self.pendings, list()

        while retry_tasks:
            args = retry_tasks.pop(0)
            self.download_single(*args, refresh=True)

    def download_history(self, files: list, refresh: bool = False) -> None:
        """Download all history files start from self.index

        :param files: a list of file_ids, range [0, 3]
        :param refresh: refresh the existing files with new downloads, default False
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

            # download files
            for id in files:
                indicator = self.download_single(self.index, id, refresh)
                # no record found --> all history files are retrieved
                if indicator == 2:
                    break

            self.index += 1

            # update resume-from every 50 files
            if self.index % 50 == 0:
                self.config[
                    "resume-from"] = self.index if not self.pendings else self.pendings[
                        0][0]
                write_config(self.config_path, self.config, self.logger)

        self.index -= 1
        self.logger.debug("Stop update")

        # if there exists failed tasks
        if self.pendings:
            # save the index of the first failed task to config
            self.logger.warning("There exist failed tasks")
            self.config["resume-from"] = self.pendings[0][0]
        # no failed
        else:
            # save the next index to config
            self.logger.info("All Success")
            self.config["resume-from"] = self.index

        write_config(self.config_path, self.config, self.logger)

    def download_specify(self,
                         files: list,
                         today_only: bool = False,
                         refresh: bool = False) -> None:
        """Download the specified files of today or last trade date

        :param files: a list of file_ids, range [0, 3]
        :param today_only: only download today files if True, else download last trade date file
        :param refresh: refresh the existing files with new downloads, default False
        """

        if self.pendings:  # retry first
            self.retry()

        # check if trade date
        if today_only and not self.is_trade_date(datetime.now()):
            self.logger.warning("Today isn't a trade date")
            return

        today = datetime.today()
        index, date = date_to_index(today, self.headers_pool, self.logger)

        if index == 0:
            self.logger.warning("Fail to get index")
            return

        # download files
        if not today_only or (today - date).days == 0:
            for id in files:
                self.download_single(index, id, refresh)
            self.logger.info("Success to download")
            return

        self.logger.warning("Today files haven't been uploaded")

    def download_single(self,
                        index: int,
                        file_id: int,
                        refresh: bool = False) -> int:
        """Download a single file on specified date

        :param index: the index of the trade date
        :param file_id: the file to download:
            0: WEBPXTICK_DT-*.zip
            1: TickData_structure.dat
            2: TC_*.txt
            3: TC_structure.dat
        :param refresh: refresh the existing files with new downloads, default False
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
            self.pendings.append((index, file_id))
            self.logger.error(
                "Fail to download/write: index %d, file_id %d; retry later" %
                (index, file_id))
            return 1

        # index out of range
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

                if self.datestr == "":  # try to get the exact date
                    kwargs = self.get_download.copy()
                    kwargs["url"] += str(index) + self.file_folder[0][0]
                    r_temp = get(kwargs, self.headers_pool, self.logger)

                    try:
                        self.datestr = re.findall(
                            r".+(-[0-9]+\.).+",
                            r_temp.headers["Content-Disposition"])[0]
                    except Exception:
                        pass

                temp = filename.split(".")
                mid = self.datestr if self.datestr != "" else f"-{index}."
                filename = temp[0] + mid + temp[1]

            # failed to write the file, add this task to pendings
            if not write(self.file_folder[file_id][1], filename, r,
                         self.logger, refresh):
                self.logger.error(
                    "Fail to download/write: index %d, file_id %d; retry later"
                    % (index, file_id))
                self.pendings.append((index, file_id))
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
