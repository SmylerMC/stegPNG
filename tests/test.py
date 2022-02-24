#!/usr/bin/env python3

import stegpng
from PIL import Image
from time import time

img1 = stegpng.open('test.png')
width, height = img1.size

img2 = Image.new('RGBA', img1.size)

st = time()
for x in range(width):
    for y in range(height):
        #print((x, y))
        pixel = img1.getpixel((x, y))
        img2.putpixel((x, y), pixel)
l = time() - st

print('{} s; {} ms/pixel'.format(l, (l*1000/(width*height))))


img2.save('testls.png')
