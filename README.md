# stegPNG
A pure python 3 png library intended to make steganography and analysis easier.
The library is still in alpha and misses lots of planned content.
Part of a future project.

## Example:
```
import stegpng
img = stegpng.open('test.png')
#We can manipulate the chunks directly
chunk = img.chunks[0] #The first chunk of a png file should always be IHDR
if chunk.type != "IHDR":
  print("Not a valid png")
  exit()
chunk['size'] = chunk['width'], int(chunk['height'] / 2) #This has a chance to break the image, but could also hide half of it.
#Or, a much quicker solution which only works for the size of the image:
img.size = img.width, int(img.height/2)
img.save('test.png)
```

## What is already implemented or not:
- [x] Png file decoding
- [x] A few chunks' content decoding (see the list bellow)
- [ ] Various automated steganography methods
- [ ] Documentation
- [ ] Anything you would like me to implement

## Installation:
There are several ways to install stegpng, see below.

### PIP
Using pip is probably the easiest way to install a python package:
```
pip3 install stegpng
```
You may need to run the command with elevated priviledges.

### Github
If you really want the latest version, clone the repository:
```
git clone https://github.com/WHGhost/stegPNG
```

And then, run setup.py:
```
./stegPNG/setup.py install
```

### Installing in editable mode:
First, clone the github repository, and then, from the git repository, run
```
pip3 install -e .
```

### PNG chunks support:
- [x] IHDR
- [ ] PLTE
- [ ] IDAT
- [x] IEND
- [ ] tRNS
- [x] cHRM
- [x] gAMA
- [ ] iCCP
- [ ] sBIT
- [x] sRGB
- [x] tEXt
- [x] iTXt
- [x] zTXt
- [x] bKGD
- [x] pHYs
- [ ] sPLT
- [x] tIME
- [ ] Any other proprietary chunk
