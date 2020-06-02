import re
import sys
import math
import subprocess
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPixmap, QPainter, QFont, QFontDatabase
from PIL import Image

def fetch_utf8(code):
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
        # fault
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

'''
================== byte layout    ======================= screen
       | msb ............ lsb     (0,0)  (1,0) ..............
0x00   | 07  ............ 0       (0,1)  (1,1) ..............
0x01   | 15  ............ 8        .      .    ..............
.      |  .  ............ .        .      .    ..............
.      |  .  ............ .        .      .    ..............
.      |  .  ............ .        .      .    ..............
.      |  .  ............ .        .      .    ..............
.      |  .  ............ .        .      .    ..............
.      |  .  ............ .       (0,h)  (1,h) ..............
==============================    ==============================

==============================    ==============================
MODE 0 =======================    MODE 1 =======================
=================== pix layout    =================== pix layout
n - 1 2n - 1 ..............       0     n       .............
.     .      ..............       1     n + 1   .............
.     .      ..............       2     n + 2   .............
.     .      ..............       .     .       .............
2     n + 2  ..............       .     .       .............
1     n + 1  ..............       .     .       .............
0     n      ..............       n - 1 2n - 1  .............
==============================    ==============================

==============================    ==============================
MODE 2 =======================    MODE 3 =======================
=================== pix layout    =================== pix layout
.     .     .     ..... .         0     1     2     ..... n
.     .     .     ..... .         n     n + 1 n + 2 ..... 2n - 1
.     .     .     ..... .         .     .     .     ..... .
.     .     .     ..... .         .     .     .     ..... .
.     .     .     ..... .         .     .     .     ..... .
n     n + 1 n + 2 ..... 2n - 1    .     .     .     ..... .
0     1     2     ..... n         .     .     .     ..... .
==============================    ==============================
'''

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

    bmp.save('tmp.png')
    png                 = Image.open('tmp.png')
    png                 = png.convert('1')
    font_area           = cell_width * cell_height
    mod                 = []
    lut                 = []

    def mode0(i):
        return int(i / cell_height), cell_height - int(i % cell_width) - 1

    def mode1(i):
        return int(i / cell_height), int(i % cell_width)

    def mode2(i):
        return int(i % cell_height), cell_height - int(i / cell_width) - 1

    def mode3(i):
        return int(i % cell_height), int(i / cell_width)

    make = [mode0, mode1, mode2, mode3][mode]

    for utf8 in unicodes:
        code            = utf8.encode('utf-16-le')
        lut.append('0x%.4x, ' % (code[1] << 8 | code[0]))

    for offset_x in range(0, cell_width * count, cell_width):
        byte            = 0
        mod.append('{ ')

        for i in range(0, font_area):
            # 8 bit max per byte
            if  i > 0 and i % 8 == 0:
                mod.append('0x%.2x, ' % byte)
                byte    = 0

            x, y        = make(i)
            x          += offset_x
            v           = png.getpixel((x, y))

            if  v == 0:
                byte   |= 1 << (i & 0x7)

        mod.append('0x%.2x, }, ' % byte)

    byte_per_char       = math.ceil(1.0 * font_area / 8)

    # cpp code
    cpp_code            = '''#pragma once
    #include<stdint.h>
    #include<stdlib.h>

    // in .data segment (in RAM)
    const     uint16_t map_unicode [] = { %s };

    // in .rodata segment (in FLASH)
    // bitmap
    constexpr uint8_t  mod_font    [][%d] = { %s };

    template<class callback>
    inline int stopix(const char * str, callback const & draw){
        auto more           = 0;
        auto unicode        = 0;
        auto i              = 0;

        struct cmp_t{
            static int invoke(const void * left, const void * right){
                return int(*(uint16_t *)left) - int(*(uint16_t *)right);
            }
        };

        for(; str[0]; str++){
            auto mask       = 0xf0 & str[0];

            // utf8 to utf16-le
            if (more > 0){
                more       -= 1;
                unicode   <<= 6;
                unicode    |= str[0] & 0x3f;
            }
            else if (str[0] < 0x80){
                unicode     = str[0];
            }
            else if (mask >= 0xe0){
                unicode     = str[0] & 0xf;
                more        = 2;
            }
            else if (mask >= 0xc0){
                unicode     = str[0] & 0x1f;
                more        = 1;
            }

            if (more != 0){
                continue;
            }

            auto find = (uint16_t *)bsearch(
                & unicode,
                map_unicode, 
                sizeof(map_unicode) / sizeof(map_unicode[0]), 
                sizeof(map_unicode[0]),
                & cmp_t::invoke
            );

            if (find == nullptr){
                // miss .............
                // need handle it
                continue;
            }

            draw(i, mod_font[find - map_unicode])
            i              += 1;
        }
    }
    '''

    cpp_code            = cpp_code % (''.join(lut), byte_per_char, ''.join(mod))
    cpp_code            = cpp_code

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
    vals            = []
    r               = str(sub.communicate()[0], 'utf-8')
    r               = r.replace('\r\n', '\n').replace('\r', '\n')
    r               = r.split('\n')

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

    # just fetch non-ascii utf8 code
    utf16_list      = [chr(i) for i in range(32, 127)]
    utf16_list     += fetch_utf8(vals)
    bits            = create(
        font='宋体', 
        font_size=12, 
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
    generate(['-dump=arm-none-eabi-objdump', '-bin=C:/Users/leon/Documents/git/stm32/demo/build/demo.elf', '-o=demo'])
    app.exec()

# call main
main()
