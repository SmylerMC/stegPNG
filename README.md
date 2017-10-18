# stegPNG
A pure python 3 png library intended to make steganography and analysis easier.
The library is still in alpha and misses lots of planned content.
Part of a future project.

## Example:
```
import stegpng
img = stegpng.open('test.png')
chunk = img.chunks[0] #The first chunk of a png file should always be IHDR
if chuk.type != "IHDR":
  print("Not a valid png")
  exit()
chunk['size'] = chunk['width'], int(chunk['height'] / 2) #This has a chance to break the image, but could also hide half of it.
img.save('test.png)
```

## What is already implemented or not:
- [x] Png file decoding
- [x] A few chunks' content decoding (see the list bellow)
- [ ] Various automated steganography methods
- [ ] Documentation
- [ ] Anything you would like me to implement

## Installation:
Clone the repository:
```git clone https://github.com/WHGhost/stegPNG```

Run setup.py:
```stegPNG/setup.py install```

### PNG chunks support:
- [x] IHDR
- [ ] PLTE
- [ ] IDAT
- [x] IEND
- [ ] tRNS
- [ ] cHRM
- [x] gAMA
- [ ] iCCP
- [ ] sBIT
- [x] sRGB
- [x] tEXt
- [ ] iTXt
- [x] zTXt
- [ ] bKGD
- [ ] pHYs
- [ ] sPLT
- [x] tIME
- [ ] Any other proprietary chunk
