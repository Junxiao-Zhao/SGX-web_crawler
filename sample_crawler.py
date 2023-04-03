import time
import pprint
import schedule
import argparse
import logging
import logging.config
from logging_tree import printout
from sgx_crawler import sgx_crawler, load_config

descrip = "This is a sample crawler to retrieve files from https://www.sgx.com/research-education/derivatives#Historical%20Commodities%20Daily%20Settlement%20Price"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=descrip)

    # version
    parser.add_argument("-v",
                        "--version",
                        const="1.0",
                        type=str,
                        nargs="?",
                        help="print the version of the script")
    # download files
    parser.add_argument("-f",
                        "--files",
                        action="extend",
                        nargs="*",
                        type=int,
                        choices=[0, 1, 2, 3],
                        help="""specify the download files (all by default):
                                    0: WEBPXTICK_DT-*.zip;
                                    1: TickData_structure.dat;
                                    2: TC_*.txt;
                                    3: TC_structure.dat""")
    # config paths
    parser.add_argument("-cc",
                        "--crawlerconfig",
                        nargs="?",
                        type=str,
                        const=None,
                        help="load the configuration file for the web crawler")
    parser.add_argument("-lc",
                        "--logconfig",
                        nargs="?",
                        type=str,
                        const=None,
                        help="load the configuration file for the logger")
    parser.add_argument("-sc",
                        "--showconfig",
                        action="store_true",
                        help="show the crawler and logger configuration")
    # type: history/today/last trade date
    parser.add_argument("-t",
                        "--type",
                        nargs=1,
                        type=str,
                        choices=["history", "today", "last"],
                        help="""specify the working type:
                                    history: all history files;
                                    today: today files (may not be available until the next trade date);
                                    last: last trade date files""")
    # mode: once/daily
    parser.add_argument("-m",
                        "--mode",
                        nargs=1,
                        type=str,
                        choices=["once", "daily"],
                        default=["once"],
                        help="""specify the workding mode (once by default):
                                    once: stop after update once;
                                    daily: update everyday""")
    # refresh
    parser.add_argument("-r",
                        "--refresh",
                        action="store_true",
                        help="refresh existing files")

    # from start
    parser.add_argument("-s",
                        "--start",
                        action="store_true",
                        help="start from 'start-from' in the config file")

    # at time
    parser.add_argument(
        "-a",
        "--at",
        type=str,
        default="20:00:00",
        nargs="?",
        help="specify everyday download time; default 20:00:00")

    # parse args
    args = parser.parse_args()
    """ pprint.pprint(vars(args))
    exit() """

    if args.version:  # -v
        print("sample crawler script version", args.version)
        exit()

    if not args.files:  # -f
        args.files = [0, 1, 2, 3]

    if args.logconfig:  # -lc
        # use given logger if the config file exists
        logconfig = load_config(args.logconfig)
        logging.config.dictConfig(logconfig)
        logger = logging.getLogger("sgx_crawler")
        logger.info("Use given logger")
    else:
        logger = None

    # create the crawler
    sgx = sgx_crawler(args.crawlerconfig, logger, args.start)

    if args.showconfig:  # -sc
        print("\n\nCrawler Configuration:")
        pprint.pprint(sgx.config)
        print("\n\nLogger Configuration:")
        printout((sgx.logger.name, sgx.logger, []))
        exit()

    # could not work without type
    if args.type is None:  # -t
        print("WARNING: --type isn't specified")
        exit()

    args.type = args.type[0]
    args.mode = args.mode[0]

    if args.mode == "once":  # -m
        sgx.logger.info("Run once")

        if args.type == "last":
            sgx.download_specify(args.files, False, args.refresh)
        elif args.type == "today":
            sgx.download_specify(args.files, True, args.refresh)
        else:
            sgx.download_history(args.files, args.refresh)

    else:
        sgx.logger.info("Run everday at %s" % args.at)
        if args.type == "last":
            schedule.every().day.at(args.at).do(sgx.download_specify,
                                                args.files, False,
                                                args.refresh)
        elif args.type == "today":
            schedule.every().day.at(args.at).do(sgx.download_specify,
                                                args.files, True, args.refresh)
        else:
            schedule.every().day.at(args.at).do(sgx.download_history,
                                                args.files, args.refresh)

        while True:
            schedule.run_pending()
            time.sleep(1)
