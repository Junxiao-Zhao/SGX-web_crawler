import os
import argparse
import logging
import logging.config
from datetime import datetime
from sgx_crawler import sgx_crawler, load_config

descrip = "This is a sampel crawler to retrieve files from https://www.sgx.com/research-education/derivatives#Historical%20Commodities%20Daily%20Settlement%20Price"

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
                        default="once",
                        help="""specify the workding mode (once by default):
                                    once: stop after update once;
                                    daily: update everyday""")
    # refresh
    parser.add_argument("-r",
                        "--refresh",
                        action="store_true",
                        help="refresh existing files")

    # parse args
    args = parser.parse_args()

    if args.version:  # --version
        print("sample crawler script version", args.version)
        exit()

    # could not work without --type
    elif args.type is None:
        print("WARNING: --type isn't specified")
        exit()

    if not args.files:  # --files
        args.files = [0, 1, 2, 3]

    if args.logconfig:  # --logconfig
        # use given logger if the config file exists
        logconfig = load_config(args.logconfig)
        logging.config.dictConfig(logconfig)
        logger = logging.getLogger("sgx_crawler")
        logger.info("Use given logger")
    else:
        logger = None

    # sgx = sgx_crawler(args.crawlerconfig, logger)
    print(args)

    # if args.mode == "once":
