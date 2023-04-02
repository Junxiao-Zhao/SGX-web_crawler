import os
import json
import logging
import requests
from time import sleep
from random import randint


def load_config(config_path: str, logger: logging.Logger = None) -> dict:
    """Load the configuration

    :param config_path: the path of the configuration file
    :param logger: the Logger, default None
    :return: the configuration
    """

    try:
        with open(config_path, 'r') as cfg:
            config = json.load(cfg)

        if logger:
            logger.debug("Success to load file: '%s'" % config_path)

        return config

    except Exception as e:
        if logger:
            logger.error(e, exc_info=False)
        else:
            print(e)
        exit()


def write_config(config_path: str, config: dict,
                 logger: logging.Logger) -> None:
    """Write the configuration

    :param config_path: the path of the configuration file
    :param config: the configuration
    :param logger: the Logger, default None
    """
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f)
    except Exception as e:
        logger.exception(e, exc_info=False)


def get(kwargs: dict, headers_pool: list,
        logger: logging.Logger) -> requests.Response:
    """Get the data from the website with random headers; try 3 times before failed
    
    :param kwargs: the parameters of requests.get (except headers)
    :param headers_pool: a list of headers
    :param logger: the Logger
    :return: the response from the website (None if failed)
    """

    i = 3  # try 3 times at most
    while i > 0:
        try:
            headers = headers_pool[randint(
                0,  # random headers each time
                len(headers_pool) - 1)]
            r = requests.get(**kwargs, headers=headers)
            return r

        except Exception as e:
            logger.exception(e, exc_info=False)

        # sleep 30s before next try
        if i > 0:
            sleep(30)
        i -= 1

    return None


def write(folder: str,
          filename: str,
          r: requests.Response,
          logger: logging.Logger,
          replace: bool = False) -> bool:
    """Write downloads to disk

    :param folder: the folder to store the file
    :param r: the response from the website
    :param logger: the Logger
    :param replace: replace the existing files with new downloads, default False
    :return: True if success else False
    """

    # create folder if not exists
    if not os.path.exists(folder):
        logger.info("Create the directory: '%s'" % folder)
        os.makedirs(folder)

    # config the path
    file_path = os.path.join(folder, filename)

    # if exists, no need to write
    if os.path.exists(file_path) and not replace:
        logger.debug("File '%s' already exists" % filename)
        return True
    # write file
    else:
        try:
            with open(file_path, 'wb') as f:
                for data in r.iter_content(chunk_size=512):
                    f.write(data)
            logger.debug("Success to write file: '%s'" % filename)
            return True

        # failed
        except Exception as e:
            logger.exception(e, exc_info=False)
            return False
