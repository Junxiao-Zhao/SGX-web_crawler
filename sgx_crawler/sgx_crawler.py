import os
import re
import json
import logging
import logging.config
from datetime import datetime
from .utils import load_config, write_config, get, write, date_to_index

local_crawler_config = os.path.join(os.path.dirname(__file__),
                                    'crawlerconfig.json')
local_log_config = os.path.join(os.path.dirname(__file__), 'logconfig.json')
default_filenames = [
    "WEBPXTICK_DT-%s.", "TickData_structure-%s.", "TC-%s.", "TC_structure-%s."
]


class sgx_crawler:

    def __init__(self,
                 config_path: str = None,
                 logger: logging.Logger = None,
                 from_start=False) -> None:
        """A crawler to download SGX data

        :param config_path: the path of the configuration file; if None then use default
        :param logger: the Logger; if None then use default
        :param from_start: start from "start-from" if True else from "resume-from"
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
            else:
                self.logger.info("Use given configuration")

            self.config_path = config_path
            self.config = load_config(self.config_path, logger)
            self.get_trade_date = self.config["get-trade-date"]
            self.get_download = self.config["get-download"]
            self.headers_pool = self.config["headers-pool"]
            self.file_folder = list(self.config["file-folder"].items())
            self.index = max(self.config["start-from"],
                             1) if from_start else max(
                                 self.config["resume-from"], 1)

            # failed tasks waiting for retrying
            self.pendings = self.config[  # load failed tasks when resume
                "failed-tasks"] if not from_start else list()
            self.max_pending_len = self.config["max-pending-length"]
            self.datestr = [0, ""]

            if self.pendings:  # retry first
                self.retry()

        except Exception as e:
            self.logger.exception(e, exc_info=False)
            exit()

    def retry(self) -> None:
        """Retry the failed tasks"""

        self.logger.info("Resuming failed tasks...")
        num_pending = len(self.pendings)
        retry_tasks, self.pendings = self.pendings, list()
        last_datestr = self.datestr.copy()

        while retry_tasks:
            args = retry_tasks.pop(0)
            self.download_single(*args, refresh=True)

        remain = len(self.pendings)
        self.logger.info("Finish resume: total %d, success: %d, fail: %d" %
                         (num_pending, num_pending - remain, remain))

        self.datestr = last_datestr

        # write to file
        self.config["failed-tasks"] = self.pendings
        write_config(self.config_path, self.config, self.logger)

    def download_history(self, files: list, refresh: bool = False) -> None:
        """Download all history files start from self.index

        :param files: a list of file_ids, range [0, 3]
        :param refresh: refresh the existing files with new downloads, default False
        """

        leave = False
        try:
            if self.pendings:
                self.retry()

            last_date = self.get_last()
            while self.datestr[1] != last_date:

                # stop when having too many failed tasks
                if len(self.pendings) > self.max_pending_len:
                    self.logger.critical("Over %d tasks failed; retry" %
                                         self.max_pending_len)

                    # try to resume
                    self.retry()

                    # cannot resume any of them
                    if len(self.pendings) >= self.max_pending_len:
                        self.logger.critical(
                            "Retry failed -- Check Internet Connection")

                        self.index += 1
                        break

                # download files
                for id in files:
                    # indicator =
                    self.download_single(self.index, id, refresh)
                    """ # no record found on current index
                    if indicator == 2:
                        break """

                self.index += 1

                # update status every 50 index
                if self.index % 50 == 0:
                    self.config["resume-from"] = self.index
                    self.config["failed-tasks"] = self.pendings
                    write_config(self.config_path, self.config, self.logger)

        except KeyboardInterrupt:
            self.logger.exception("Keyboard Interrupt; Stop downloading",
                                  exc_info=False)
            leave = True

        self.index -= 1
        self.logger.debug("Stop update")

        if not leave and self.pendings:  # retry failed tasks
            self.retry()

        if self.pendings:
            self.logger.warning("There exist failed tasks")
        else:
            self.logger.info("All Success")

        self.config["resume-from"] = self.index
        self.config["failed-tasks"] = self.pendings
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

        # check if trade date
        if today_only and not self.is_trade_date(datetime.now()):
            self.logger.warning(
                "Today isn't a trade date/Today's files haven't been uploaded")
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
            self.logger.info("Finish")
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
            2: no record found
            3: success
        """

        # check file_id
        if file_id < 0 or file_id > 3:
            self.logger.warning("file_id out of range [0, 3]")
            return 0

        # check index
        if index < 1:
            self.logger.warning("index out of range [1, ]")
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
            self.logger.warning("File not found: '%s', index %d" %
                                (default_filenames[file_id][:-4], index))
            return 2

        # the right file
        elif r.headers["Content-Type"] == "application/download":
            # extract the filename
            filename = re.findall(r"[\S]+\s[a-z]+=([\S]+)",
                                  r.headers["Content-Disposition"])[0]

            # if we don't have the date
            if self.datestr[0] != index:
                # extract date from filename
                filedate = re.findall(r"[0-9]+", filename)
                if filedate:  # if filename contains date
                    self.datestr = [index, filedate[0]]

                # extract from WEBPXTICK_DT-*.zip
                else:
                    kwargs = self.get_download.copy()
                    kwargs["url"] += str(index) + self.file_folder[2][0]
                    kwargs["stream"] = True  # just get filename
                    r_temp = get(kwargs, self.headers_pool, self.logger)

                    try:
                        filedate = re.findall(
                            r"[0-9]+",
                            r_temp.headers["Content-Disposition"])[0]
                        self.datestr = [index, filedate]
                    except Exception:
                        self.logger.warning(
                            "Fail to get the date; use index in the filename instead"
                        )

            name_ext = filename.split(".")
            mid = self.datestr[1] if self.datestr[0] == index else str(index)
            # use extension from filename if exists else use default
            ext = name_ext[1] if len(
                name_ext) == 2 else self.file_folder[file_id][0].split(".")[1]
            filename = default_filenames[file_id] % mid + ext

            # failed to write the file, add this task to pendings
            if not write(self.file_folder[file_id][1], filename, r,
                         self.logger, refresh):
                self.logger.error(
                    "Fail to download/write: index %d, file_id %d; add to pendings"
                    % (index, file_id))
                self.pendings.append((index, file_id))
                return 1
            # success
            return 3

    def get_last(self) -> str:
        """Get the last trade date"""

        # get recent 10 trade dates
        r = get(self.get_trade_date, self.headers_pool, self.logger)

        # failed to get the trade date
        if r is None:
            self.logger.error("Fail to get trade date")
            return None

        try:
            data = json.loads(r.content.decode())['data']
            return data[-1]["base-date"]
        except KeyError as e:
            self.logger.exception(e, exc_info=False)
            self.logger.critical("API might change")
            return None

    def is_trade_date(self, check_date: datetime) -> bool:
        """Check whether the given date is the last trade date

        :param check_date: a date
        :return: True if it's the last trade date else False
        """

        return self.get_last() == datetime.strftime(check_date, "%Y%m%d")
