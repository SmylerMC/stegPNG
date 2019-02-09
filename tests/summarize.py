#!/usr/bin/env python3

import stegpng
from sys import argv

img = stegpng.open(argv[1], ignore_signature=False)
#for chunk in img.chunks:
    #print(chunk.type)
    #print(chunk.is_supported())
    #print('='*50)



def png_chunk_summary(chunk):
    print(chunk.type)
    if not chunk.is_supported():
        print('Unsuported chunk: {}------------------------------------------------------'.format(chunk.type))
        return
    print("Valid: {}".format(chunk.is_valid()))
    if chunk.type not in ('PLTE', 'IDAT'):
        for key, val in chunk.get_payload().items():
            print("{}: {}".format(key, val))

idats = []
for indice, chunk in enumerate(img.chunks):
    if chunk.type == 'IDAT':
        idats.append(chunk)
        continue
    else:
        if len(idats) == 1:
            print("Report for chunk {}:".format(indice - 1))
            png_chunk_summary(idats[0])
            print('='*50)
        elif len(idats) > 1:
            print("Hidding {} IDAT chunks".format(len(idats)))
            idats = []
    print("Report for chunk {}".format(indice))
    png_chunk_summary(chunk)
    print('='*50)


for chunk in img.chunks:
    chunk.type = chunk.type
    chunk.update_crc()
    len(chunk)
    chunk.iscritical()
    chunk.isancillary()
    if not chunk.is_supported():
        print(' '* 50, end='\r')
        print("Found unsupported chunk: {} in {}".format(chunk.type, argv[1]))
        continue
    if chunk.type not in ('PLTE', 'IDAT'):
        for key, val in chunk.get_payload().items():
            try:
                chunk[key] = val
            except KeyError:
                pass
    chunk.is_valid()
    chunk._set_empty_data()
    img.reset()
