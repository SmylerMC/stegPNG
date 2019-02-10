#!/usr/bin/env python3

import stegpng
from sys import argv
from os import remove, rename, walk, listdir
from PIL import Image
import io
from time import time

IMG_DIR = "test_files"
FIN_DIR = IMG_DIR + "/fine"
NEW_DIR = IMG_DIR + "/new"
ERR_DIR = IMG_DIR + "/error"
CRA_DIR = IMG_DIR + "/crashers"

class UnknownChunkException(Exception):

    def __init__(self, chunk):
        self.chunk = chunk
        super(UnknownChunkException, self).__init__("Unknown chunk: {}".format(chunk.type))

def printimg(img):
    img = stegpng.open(img)
    print(img.pixels)

def move2new(directory):
    for fname in listdir(directory):
        rename(directory + "/" + fname, NEW_DIR + "/" + fname)

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

def masstest(quick=False):

    if not quick:
        print("Moving files to the new directory... ", end='')
        move2new(ERR_DIR)
        move2new(FIN_DIR)
        print("Done")

    for dirpath, dirs, files in walk(NEW_DIR):
        for fn in files:
            fname = dirpath + '/' + fn
            with open(fname, 'rb') as f:
                content = f.read()
            errors, changed, invalid, unknown_chunks = test_img(content, quick=True)
            if errors:
                print("{} threw an exception".format(fname))
                rename(fname, ERR_DIR + '/' + fn)
            elif len(unknown_chunks):
                print("{} has unknown chunks".format(fname))
                rename(fname, ERR_DIR + '/' + fn)
            elif len(invalid):
                print("{} has invalid chunks".format(fname))
                rename(fname, ERR_DIR + '/' + fn)
            else:
                print("{} is fine".format(fname))
                rename(fname, FIN_DIR + '/' + fn)

def stats():
    chunks = {}
    c = 0
    exceptions = 0
    file_count = 0
    changed_count = 0
    fnames = []
    print('Listing files...\r', end='')
    for dirpath, dirs, files in walk(IMG_DIR):
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

    usage_str = 'Usage: {} action\nPossible actions:\n\tmasstest\n\tquicktest\n\timgtest\n\tstats\n\tprint'.format(argv[0])

    try:
        if argv[1] == 'imgtest':
            test()
        elif argv[1] == 'masstest':
            masstest()
        elif argv[1] == 'quicktest':
            masstest(quick=True)
        elif argv[1] == 'stats':
            stats()
        elif argv[1] == 'print':
            printimg(argv[2])
        else:
            raise IndexError()
    except IndexError as e:
        print(usage_str)

