# A web crawler to download files from SGX

This is a web crawler to download the files (WEBPXTICK_DT-\*.zip, TickData_structure.dat, TC_\*.txt, TC_structure.dat) from [Singapore Exchange](https://www.sgx.com/research-education/derivatives#Historical%20Commodities%20Daily%20Settlement%20Price). 

### Supports:
- Accept command line options and config files
- Download both historical files and today's file based on
user's instructions
- Logging
- Auto-recover failed tasks
- Resume unfinished tasks
- Handle KeyBoard Interrupt

### Usage
    usage: sample_crawler.py [-h] [-v [VERSION]] [-f [{0,1,2,3} ...]] [-cc [CRAWLERCONFIG]] [-lc [LOGCONFIG]] [-sc] [-t {history,today,last}] [-m {once,daily}] [-r] [-s] [-a [AT]]

    This is a sample crawler to retrieve files from https://www.sgx.com/research-education/derivatives#Historical%20Commodities%20Daily%20Settlement%20Price

    optional arguments:
    -h, --help            show this help message and exit
    -v [VERSION], --version [VERSION]
                            print the version of the script
    -f [{0,1,2,3} ...], --files [{0,1,2,3} ...]
                            specify the download files (all by default): 0: WEBPXTICK_DT-*.zip; 1: TickData_structure.dat; 2: TC_*.txt; 3: TC_structure.dat
    -cc [CRAWLERCONFIG], --crawlerconfig [CRAWLERCONFIG]
                            load the configuration file for the web crawler
    -lc [LOGCONFIG], --logconfig [LOGCONFIG]
                            load the configuration file for the logger
    -sc, --showconfig     show the crawler and logger configuration
    -t {history,today,last}, --type {history,today,last}
                            specify the working type: history: all history files; today: today files (may not be available until the next trade date); last: last trade date     
                            files
    -m {once,daily}, --mode {once,daily}
                            specify the workding mode (once by default): once: stop after update once; daily: update everyday
    -r, --refresh         refresh existing files
    -s, --start           start from 'start-from' in the config file
    -a [AT], --at [AT]    specify everyday download time; default 20:00:00

### Configuration Files
- For the web crawler, see [crawlercconfig.json](./sgx_crawler/crawlerconfig.json)
- For the logging, see [logconfig.json](./sgx_crawler/logconfig.json)

### Examples
- To get the last trade date's "TC_\*.txt" and "TC_structure.dat" just once using default config files, run `python sample_crawler.py -f 2 3 -t last -m once`
- To get history data and update all four files at 18:00:00 every day using specified config files, run `python sample_crawler.py -cc "YOUR CRAWLERCONFIG" -lc "YOUR LOGCONFIG" -t history -m daily -a 18:00:00`
- To refresh all the history files from the beginning, run `python sample_crawler.py -t history -r -s`
- To manually resume unfinished tasks, run `python sample_crawler.py -t history`

### Notes
- Since the data on the website **always has one trade date delay**, so download today's data will **always fail**; Recommend to use download last trade date instead
- For some earliest dates, "TC_structure.dat" has the name "TickData_structure.dat" or "ATT\*"; It will be saved to "TC_structure-\*.dat"
- For some earliest dates, "WEBPXTICK_DT-\*.zip" has the name "\*\_web.tic", and "TC_\*.txt" has the name "\*\_web.atic1". These two will be saved to "WEBPXTICK_DT-\*.tic" and "TC_\*.atic1"
- For some earliest dates, "WEBPXTICK_DT-\*.zip" has the name "WEBPXTICK_DT-\*.gz" and will be saved as "WEBPXTICK_DT-\*.gz"
- There exist files that is not corresponding to a trade date, like those on 2023-01-02 and 2023-01-01.
