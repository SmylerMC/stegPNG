#!/usr/bin/env python3

import stegpng
from sys import argv
from os import remove, rename, walk
from PIL import Image
import io
from time import time

class UnknownChunkException(Exception):

    def __init__(self, chunk):
        self.chunk = chunk
        super(UnknownChunkException, self).__init__("Unknown chunk: {}".format(chunk.type))

def printimg(img):
    img = stegpng.open(img)
    print(img.pixels)

def test_img(imgbytes, catch=True, quick=False):
    try:
        img = stegpng.Png(imgbytes)
        pilimg = Image.open(io.BytesIO(imgbytes))
        unsupported_chunks = set()
        invalid_chunks = []
        error = False
        modified = False
        
        pilwidth, pilheight = pilimg.size
        width, height = img.size
        
        if pilwidth != width:
            raise Exception('widths does not match')
        if pilheight != height:
            raise Exception('heights does not match')

        plt = []
        if pilimg.mode == 'P':
            p = pilimg.getpalette()
            for i in range(0, len(p), 3):
                plt.append((p[i], p[i+1], p[i+2]))

        for chunk in img.chunks:
            if not chunk.is_supported():
                unsupported_chunks.add(chunk.type)
                if quick:
                    raise UnknownChunkException(chunk)
                continue
            original_bytes = chunk.bytes
            chunk.type = chunk.type
            chunk.iscritical()
            chunk.isancillary()
            if not chunk.is_valid() and not chunk.type == 'IDAT':
                invalid_chunks.append(chunk)
            if chunk.check_crc:
                chunk.update_crc()
            if chunk.type == 'PLTE':
                for i, val in enumerate(chunk.get_payload()):
                    chunk[i] = val
            else:
                payload = chunk.get_payload(ihdr=img.chunks[0])
                if type(payload) == dict:
                    for key, val in payload.items():
                        try:
                            chunk.setitem(key, val, ihdr=img.chunks[0])
                        except KeyError:
                            pass
            if chunk.bytes != original_bytes:
                modified = True
        chunk._set_empty_data()
        img.reset()

        for y in range(height):
            for x in range(width):
                p1 = img.getpixel((x, y))
                p2 = pilimg.getpixel((x, y))
                if pilimg.mode == 'P':
                    p2 = plt[p2]
                if p1 != p2:
                    raise Exception('pixels at {}:{} does not match: {}  and {}'.format(x, y, p1, p2))

        img.reset()

    except Exception as e:
        if not catch:
            raise e
        else:
            if type(e) == UnknownChunkException:
                unsupported_chunks.add(e.chunk.type)
            else:
                error = True
    return error, modified, tuple(invalid_chunks), unsupported_chunks

def test():
    fname = argv[2]
    with open(fname, 'rb') as f:
        error, modified, invalid, unknown_chunks = test_img(f.read(), catch=False)
    if len(unknown_chunks) > 0:
        print('Unknown chunks: {}'.format(str(unknown_chunks)[1:-1]))
    if len(invalid) > 0:
        print('Invalid chunks: {}'.format(str(invalid)[1:-1]))
    if error:
        print("Got an error.")
    if modified:
        print("Test did not preserve image integrity...")

def clean():
    for dirpath, dirs, files in walk('errors/'):
        for fn in files:
            fname = dirpath + fn
            with open(fname, 'rb') as f:
                content = f.read()
            errors, changed, invalid, unknown_chunks = test_img(content, quick=True)
            if errors:
                print("{} threw an exception, keeping it.".format(fname))
            #elif changed:
                #print("%s changed, moving it to changed directory.", fname)
            #    print("{} changed.".format(fname))
            elif len(unknown_chunks):
                #print("%s has unknown chunks, moving it to unknown directory", fname)
                print("{} has unknown chunks.".format(fname))
            elif len(invalid):
                #print("%s has unknown chunks, moving it to unknown directory", fname)
                print("{} has invalid chunks.".format(fname))
            else:
                print("{} is fine, deleting it.".format(fname))
                remove(fname)

def spider(url):
    from requests import Session
    from urllib.parse import urljoin, quote as url_encode
    from sys import argv
    from bs4 import BeautifulSoup as Soup
    from time import sleep, time
    import random
    import stegpng
    from stegpng import Png
    import magic
    from json import dumps

    unknown_chunks = {}
    exception_count = 0

    visited = set()
    processed_imgs = set()
    to_process = set()
    to_process.add(url)


    sess = Session()

    proxies = {
        'http': 'socks5://127.0.0.1:9050',
        'https': 'socks5://127.0.0.1:9050'
    }

    try:
        while len(to_process) > 0:
            try:

                url = to_process.pop()
                print("Spidered: {}\t To spider: {}\t Processed images: {}\t Exceptions: {}".format(
                    len(visited),
                    len(to_process),
                    len(processed_imgs),
                    exception_count,
                    ), end=' ' * 20 + '\r')
                visited.add(url)
                res = sess.get(url, proxies=proxies)
                soup = Soup(res.text, 'html.parser')
                links = [l.get('href', None) for l in soup.find_all('a')]
                links = set(map(lambda l: urljoin(url, l), links))
                links.difference_update(visited)
                to_process = to_process.union(links)

                imgs = [l.get('src', '') for l in soup.find_all('img')]
                imgs = set(filter(lambda l: l.endswith('.png'), map(lambda l: urljoin(url, l), imgs)))
                for url in imgs:
                    if url in processed_imgs:
                        continue
                    resp = sess.get(url, proxies=proxies).content
                    if magic.detect_from_content(resp).mime_type == 'image/png':
                        errors, changed, invalid, unknown_chunks = test_img(resp)
                        if len(unknown_chunks):
                            print('Unknown chunks: {} in {}'.format(str(unknown_chunks)[1:-1], url))
                        if errors or changed or len(invalid) or len(unknown_chunks):
                            exception_count += 1
                            print("Saving {}: exception: {}, unkown chunks: {}, invalid chunks: {}".format(url, errors, len(unknown_chunks), len(invalid)))
                            with open('errors/{}.png'.format(url.replace('/', '-').replace(':', '-')), 'wb') as f:
                                f.write(resp)
                    processed_imgs.add(url)
                    print("Spidered: {}\t To spider: {}\t Processed images: {}\t Saved: {}".format(
                        len(visited),
                        len(to_process),
                        len(processed_imgs),
                        exception_count,
                        ), end='\r')

            except Exception as e:
                print("An error occured: {}".format(e))
    except KeyboardInterrupt:
        print('\r'+' '*100+"\rGoodbay!")
    else:
        print()
        print("Nothing to spider!")

def stats():
    chunks = {}
    c = 0
    exceptions = 0
    file_count = 0
    changed_count = 0
    fnames = []
    print('Listing files...\r', end='')
    for dirpath, dirs, files in walk('errors/'):
        for fn in files:
            fname = dirpath + fn
            fnames.append(fname)
    print('Found {} files'.format(len(fnames)))
    start_time = time()
    for i, fname in enumerate(fnames):
        fst = time()
        avg_time = (fst - start_time)/(i+1)
        remain_time = (len(fnames)-i)*avg_time
        remain_hr = int(remain_time // 3600)
        remain_time -= remain_hr * 3600
        remain_mn = int(remain_time//60)
        remain_time -= remain_mn*60
        remain_sc = int(remain_time)
        print('Analysed {}/{} files {}h{}mn{}s remaining           '.format(
                i,
                len(fnames),
                remain_hr,
                remain_mn,
                remain_sc
            ),
            end='\r'
        )
        with open(fname, 'rb') as f:
            content = f.read()
        file_count += 1
        errors, changed, invalid, unknown_chunks = test_img(content)
        for chunk in unknown_chunks:
            c += 1
            if chunk in chunks:
                chunks[chunk] += 1
            else:
                chunks[chunk] = 1
        if errors:
            exceptions += 1
        if changed:
            changed_count += 1

    print('{} files'.format(file_count))
    print('Exception: {}, {}%'.format(exceptions, int(exceptions*100/file_count)))
    print('Changed files: {}, {}%'.format(changed_count, int(changed_count*100/file_count)))
    print('{} s/file'.format((time()-start_time)/file_count))

    print('Unknown chunks:')
    for chunk, count in chunks.items():
        freq = count/c *100
        print('\t', chunk, count ,' \t', freq)


if __name__ == '__main__':
    try:
        if argv[1] == 'test':
            test()
        elif argv[1] == 'clean':
            clean()
        elif argv[1] == 'spider':
            spider(argv[2])
        elif argv[1] == 'stats':
            stats()
        elif argv[1] == 'print':
            printimg(argv[2])
        else:
            raise IndexError()
    except IndexError as e:
        print("Invalid args...")
        raise e

