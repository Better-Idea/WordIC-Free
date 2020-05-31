from bitarray import bitarray
from PIL import Image

import re
import sys
import subprocess
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPixmap, QPainter, QFont, QFontDatabase

def fetch_unicode(code):
    utf8            = bytearray()
    lut             = []
    more            = 0

    for c in code:
        # ignore ascii code
        if  c < 0x80:
            continue

        if  more == 0:
            pass
        elif more >= 1 and (c & 0xc0) == 0x80:
            more   -= 1
            utf8.append(c)
            
            if  more != 0:
                continue

            try:
                val = utf8.decode('utf8')
                lut.append(val)
            except Exception:
                pass

            utf8.clear()
            continue
        # falt
        else:
            more    = 0
            utf8.clear()

        mask        = c & 0xf0

        # not support 
        if  mask  >= 0xf0:
            continue
        else:
            utf8.append(c)

        if  mask >= 0xe0:
            more   = 2
        elif mask >= 0xc0:
            more   = 1
        else:
            utf8.clear()

    lut.sort()
    return lut

# ================== byte layout    ======================= screen
#        | msb ............ lsb     (0,0)  (1,0) ..............
# 0x00   | 07  ............ 0       (0,1)  (1,1) ..............
# 0x01   | 15  ............ 8        .      .    ..............
# .      |  .  ............ .        .      .    ..............
# .      |  .  ............ .        .      .    ..............
# .      |  .  ............ .        .      .    ..............
# .      |  .  ............ .        .      .    ..............
# .      |  .  ............ .        .      .    ..............
# .      |  .  ............ .       (0,h)  (1,h) ..............
# ==============================    ==============================

# ==============================    ==============================
# MODE 0 =======================    MODE 1 =======================
# =================== pix layout    =================== pix layout
# n - 1 2n - 1 ..............       0     n       .............
# .     .      ..............       1     n + 1   .............
# .     .      ..............       2     n + 2   .............
# .     .      ..............       .     .       .............
# 2     n + 2  ..............       .     .       .............
# 1     n + 1  ..............       .     .       .............
# 0     n      ..............       n - 1 2n - 1  .............
# ==============================    ==============================

# ==============================    ==============================
# MODE 2 =======================    MODE 3 =======================
# =================== pix layout    =================== pix layout
# .     .     .     ..... .         0     1     2     ..... n
# .     .     .     ..... .         n     n + 1 n + 2 ..... 2n - 1
# .     .     .     ..... .         .     .     .     ..... .
# .     .     .     ..... .         .     .     .     ..... .
# .     .     .     ..... .         .     .     .     ..... .
# n     n + 1 n + 2 ..... 2n - 1    .     .     .     ..... .
# 0     1     2     ..... n         .     .     .     ..... .
# ==============================    ==============================

def create(
    font, 
    font_size, 
    cell_width, 
    cell_height, 
    unicodes,
    mode):

    count               = len(unicodes)
    font                = QFont(font, font_size)
    bmp                 = QPixmap(cell_width * count, cell_height)
    painter             = QPainter(bmp)
    x                   = 0
    last_char           = ''
    bmp.fill()
    painter.setPen(Qt.black)
    painter.setFont(font)

    for c in unicodes:
        # ignore the repeat char
        if  last_char == c:
            continue
        else:
            last_char = c
        print(c)

        painter.drawText(x, 0, cell_width, cell_height, Qt.AlignCenter, c)
        x              += cell_width

    bmp.save('.tmp.png')
    png                 = Image.open('.tmp.png')
    png                 = png.convert('1')
    font_area           = cell_width * cell_height
    bits                = bitarray()

    def mode0(offset_x):
        for i in range(0, font_area):
            x           = int(i / cell_height)
            y           = int(i % cell_width)
            x          += offset_x
            v           = png.getpixel((x, cell_height - y - 1))
            bits.append(v == 0)
    
    def mode1(offset_x):
        for i in range(0, font_area):
            x           = int(i / cell_height)
            y           = int(i % cell_width)
            x          += offset_x
            v           = png.getpixel((x, y))
            bits.append(v == 0)

    def mode2(offset_x):
        for i in range(0, font_area):
            x           = int(i % cell_width)
            y           = int(i / cell_height)
            x          += offset_x
            v           = png.getpixel((x, cell_height - y - 1))
            bits.append(v == 0)
    
    def mode3(offset_x):
        for i in range(0, font_area):
            x           = int(i % cell_width)
            y           = int(i / cell_height)
            x          += offset_x
            v           = png.getpixel((x, y))
            bits.append(v == 0)

    make = [mode0, mode1, mode2, mode3][mode]

    for utf8, offset_x in zip(unicodes, range(0, font_area * count, font_area)):
        v               = utf8.encode('utf-16-le')
        v               = bitarray().frombytes(v)
        # bits           += v
        make(offset_x)

    return bits
            

def generate(argv):
    arg_dump        = '-dump'
    arg_bin         = '-bin'
    arg_o           = '-o'

    args            = [arg_dump, arg_bin, arg_o]
    tab             = dict()

    for i in argv:
        [k, v] = i.split('=')
        tab.setdefault(k, v)

    miss_arg = False

    for arg in args:
        if  arg not in tab:
            print('miss param', arg)
            miss_arg = True

    if  miss_arg:
        return

    # invoke objdump for get .rodata segment data
    v_dump          = tab.get(arg_dump)
    v_bin           = tab.get(arg_bin)
    v_o             = tab.get(arg_o)
    cmd             = '%s -j .rodata -s %s' % (v_dump, v_bin)
    sub             = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    sub.wait()
    r               = str(sub.communicate()[0], 'utf-8').split('\n')
    vals            = []

    for line in r[4:]:
        items = re.match(r' [0-9a-f]+ ([0-9a-f]{8}) ([0-9a-f ]{8}) ([0-9a-f ]{8}) ([0-9a-f ]{8})', line)

        if  items is None:
            continue

        for v in items.groups():
            v       = str(v)

            if  v.replace(' ', '') == '':
                break

            v       = int(v, 16).to_bytes(4, 'big')
            vals   += v

    utf16_list      = fetch_unicode(vals)
    bits            = create(
        font='WenQuanYi Bitmap Song', 
        font_size=16, 
        cell_width=16, 
        cell_height=16,
        unicodes=utf16_list,
        mode=0
    )

def main():
    app = QApplication(sys.argv)
    fonts = QFontDatabase().families()
    for f in fonts:
        print(f)
    generate(['-dump=~/software/gcc-arm-none-eabi-9/bin/arm-none-eabi-objdump', '-bin=~/git/stm32/demo/demo/build/demo.elf', '-o=demo'])
    app.exec()

# call main
main()
