#!/usr/bin/env python3

from requests import Session
from urllib.parse import urljoin, quote as url_encode
from sys import argv
from bs4 import BeautifulSoup as Soup
import magic
from os import listdir, walk
from os.path import isfile, getsize
from time import strftime


sess = Session()
proxies = {
    'http': 'socks5://127.0.0.1:9050',
    'https': 'socks5://127.0.0.1:9050'
}


visited = set()
logname = None
logfile = None
req_count = 0
data_size = 0

IMG_DIR = "test_files" #Where to save scraped files
LOG_DIR = "scraperlogs"    #Where to save logs


class VisitedException(Exception):

    def __init__(self, url):
        self.url = url
        super(VisitedException, self).__init__("Already visited {}".format(self.url))

def get_directory_size(directory):
    size = 0
    for cdir, dirlist, flist in walk(directory):
        for f in flist:
            size += getsize(cdir + '/' + f)
    return size

def format_size2human(size, is_units=False):
    units_cs = ['o', 'Kio', 'Mio', 'Gio', 'Tio'] # Computer Science Units
    units_is = ['o', 'Ko', 'Mo', 'Go', 'To'] # International System Units
    ratio_cs = 1024
    ratio_is = 1000
    unit = 0
    if is_units:
        units = units_is
        ratio = ratio_is
    else:
        units = units_cs
        ratio = ratio_cs
    while size >= ratio and unit < len(units) - 1:
        size /= ratio
        unit += 1
    return "{} {}".format(round(size, 1), units[unit])

def load():
    global logfile
    global logname
    global data_size
    print("Loading previous logs...")
    log_count = 0
    for fname in listdir(LOG_DIR): # We are only interested in the top directory
        fname = LOG_DIR + "/" + fname
        if not isfile(fname):
            continue
        with open(fname, 'r') as f:
            while True:
                line = f.readline()
                if not line:
                    break
                if line[0] == '#':
                    continue
                if line[:4] != 'http':
                    print('Ignored invalid http(s) url: {}'.format(line))
                    continue
                visited.add(line.strip())
        log_count += 1
    print("Loaded {} log files ({} urls)".format(log_count, len(visited)))
    print("Calculating current amount of data...")
    data_size = get_directory_size(IMG_DIR)
    print("We already have {} worth of data.".format(format_size2human(data_size, is_units=True)))
    logname = "{}/scraper-{}.log".format(LOG_DIR, strftime("%Y-%m-%d-%H-%M-%s"))
    logfile = open(logname, 'w')
    logfile.write("#Started on {}, {} previous urls loaded\n".format(strftime("%c"), len(visited)))
    print("Created new log:", logname)


def save():
    logfile.write("#Terminated on {}, made {} requests\n".format(strftime("%c"), req_count))
    logfile.close()

def has_visited(url):
    return url in visited


def request(url):
    global req_count
    if has_visited(url):
        raise VisitedException(url)
    resp = sess.get(url, proxies=proxies)
    logfile.write(url + "\n")
    req_count += 1
    return resp


def scrap(starturl, limit):
    
    global data_size
    
    visited_count = 0
    img_count = 0

    queue = set()    
    queue.add(starturl)

    def print_stats():
        print(
            "Visited pages {} | Saved images: {} | Queue: {} | Data: {}/{}".format(
                visited_count,
                img_count,
                len(queue),
                format_size2human(data_size, is_units=True),
                format_size2human(limit, is_units=True),
            ),
            end="\r"
        )

    while len(queue) > 0 and data_size < limit:

        url = queue.pop()

        # Get new URLs (from <a> href tags only)
        try:
            resp = request(url)
        except VisitedException:
            continue
        except Exception as e:
            print("Failed to download URL ({}): {}".format(e, img_url))
            continue
        try:
            soup = Soup(resp.text, 'html.parser')
            links = [l.get('href', None) for l in soup.find_all('a')]
            links = set(map(lambda l: urljoin(url, l), links)) #Make relative links absolute
            # Remove the already visited links from the new one
            links.difference_update(visited)
            queue.update(links)
        except Exception as e:
            print("Failed ({}) to parse page at {}".format(e, url))
            continue

        # Get image URLs from <img> tags
        imgs = [l.get('src', '') for l in soup.find_all('img')]
        imgs = set(filter(lambda l: l.endswith('.png'), map(lambda l: urljoin(url, l), imgs)))
        imgs.difference_update(visited)
        for img_url in imgs:
            if has_visited(img_url):
                continue
            try:
                resp = request(img_url).content
                visited.add(img_url)
            except VisitedException:
                continue
            except Exception as e:
                print("Failed to download URL ({}): {}".format(e, img_url))
                continue
                
            if not magic.detect_from_content(resp).mime_type == 'image/png':
                continue
                
            savename = img_url.replace('/', '-').replace(':', '-')
            savename = savename[:50]
            savename = '{}/new/{}.png'.format(IMG_DIR, savename)
            with open(savename, 'wb') as f:
                f.write(resp)
            if img_count % 20 == 0:
                print("Recalculating the amount of the data we already have...         ", end='\r')
                data_size = get_directory_size(IMG_DIR)
            else:
                data_size += len(resp)
            img_count += 1
            print_stats()
            if data_size >= limit:
                print("Downloaded enough data!")
                return
        visited_count += 1
        print_stats()
        visited.add(url)


    else:
        print("Nothing to spider! (Was your starting url valid?)")

if __name__ == '__main__':
    if len(argv) != 3:
        print("Usage: {} start_url limit".format(argv[0]))
        exit(1)
    load()
    try:
        limit = int(argv[2])
    except:
        print("Invalid limit!")
        exit(2)
    try:
        scrap(argv[1], limit)
    except KeyboardInterrupt:
        # we got out of scrap, let's let it save everything...
        pass
    print("Saving...")
    save()
