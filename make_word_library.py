import re
import os
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

# cpp code
cpp_code            = '''#pragma once
#include<stdint.h>
#include<stdlib.h>

// in .data segment
%s

// in .rodata segment
// bitmap
%s
%s

struct mod_t{
    static constexpr uint32_t ascii_width      = %d;
    static constexpr uint32_t ascii_height     = %d;
    static constexpr uint32_t unicode_width    = %d;
    static constexpr uint32_t unicode_height   = %d;

    bool is_ascii(){
        return bmp_bytes == sizeof(mod_ascii[0]);
    }

    bool is_unicode(){
        return bmp_bytes == sizeof(mod_unicode[0]);
    }

    bool width(){
        return bmp_bytes == sizeof(mod_ascii[0]) ? ascii_width : unicode_width;
    }

    bool height(uint32_t bytes){
        return bmp_bytes == sizeof(mod_ascii[0]) ? ascii_height : unicode_height;
    }

    operator const uint8_t * (){
        return bmp;
    }

    uint32_t size(){
        return bmp_bytes;
    }
private:
    const uint8_t * bmp;
    uint32_t        bmp_bytes;
};

// FULL NAME:
// string to pix
//
// RETURN:
// the characters count of the string (str)
//
// NOTE:
// the param 'draw' can be a lambda or normal function with 2 args as the follow signature
// void draw(int current_char_index, mod_t mod);
// 
// REFERENCE:
// ...
// stopix(str, [&](int i, mod_t mod){
//     put(mod, mod.size());
// });
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

        if (unicode < 0x20){
            // not printable
            // --------------------------
            continue;
        }

        if (unicode < 0x80){
            draw(i, mod_ascii[unicode - 0x20], sizeof(mod_ascii[0]));
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

        draw(i, mod_unicode[find - map_unicode], sizeof(mod_unicode[0]))
        i              += 1;
    }
    return i;
}
'''

def create_map_unicode(unicodes):
    lut                 = []
    for utf8 in unicodes:
        code            = utf8.encode('utf-16-le')
        lut.append('0x%.4x, ' % (code[1] << 8 | code[0]))
    return lut

def create_mod(
    font, 
    font_size, 
    cell_width, 
    cell_height, 
    unicodes,
    mode):

    count               = len(unicodes)
    font                = QFont(font, font_size)
    bmp                 = QPixmap(cell_width * count, cell_height)
    painter             = QPainter()
    x                   = 0
    last_char           = ''
    bmp.fill()
    painter.begin(bmp)
    painter.setPen(Qt.black)
    painter.setFont(font)

    for c in unicodes:
        # ignore the repeat char
        if  last_char == c:
            continue
        else:
            last_char = c

        painter.drawText(x, 0, cell_width, cell_height, Qt.AlignCenter, c)
        x              += cell_width

    painter.end()

    tmp_img             = 'tmp.png'
    bmp.save(tmp_img)
    png                 = Image.open(tmp_img)
    png                 = png.convert('1')
    font_area           = cell_width * cell_height
    mod                 = []

    def mode0(i):
        return int(i / cell_height), cell_height - int(i % cell_width) - 1

    def mode1(i):
        return int(i / cell_height), int(i % cell_width)

    def mode2(i):
        return int(i % cell_height), cell_height - int(i / cell_width) - 1

    def mode3(i):
        return int(i % cell_height), int(i / cell_width)

    make = [mode0, mode1, mode2, mode3][mode]

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

    os.remove(tmp_img)
    byte_per_char       = math.ceil(1.0 * font_area / 8)
    return byte_per_char, mod

def create_file(
    font, 
    font_size, 
    cell_width, 
    cell_height, 
    unicodes,
    mode,
    output):
    mod_ascii_w     = cell_width >> 1
    mod_ascii_h     = cell_height
    mod_unicode_w   = cell_width
    mod_unicode_h   = cell_height

    ascii_list      = [chr(i) for i in range(32, 128)]
    map_unicode     = create_map_unicode(unicodes)
    map_unicode     = 'const     uint8_t  map_unicode []     = { %s };' % (''.join(map_unicode))
    cell_size, mod  = create_mod(font, font_size, mod_ascii_w, mod_ascii_h, ascii_list, mode)
    mod_ascii       = 'constexpr uint8_t  mod_ascii   [][%d] = { %s };' % (cell_size, ''.join(mod))
    cell_size, mod  = create_mod(font, font_size, mod_unicode_w, mod_unicode_h, unicodes, mode)
    mod_unicodes    = 'constexpr uint8_t  mod_unicode [][%d] = { %s };' % (cell_size, ''.join(mod))

    with open(output, 'w') as f:
        f.write(cpp_code % (
            map_unicode, 
            mod_ascii, 
            mod_unicodes, 
            mod_ascii_w, 
            mod_ascii_h, 
            mod_unicode_w, 
            mod_unicode_h
        ))
        f.close()

def generate(argv):
    arg_font        = '-f'
    arg_size        = '-s'
    arg_mode        = '-m'
    arg_w           = '-w'
    arg_h           = '-h'
    arg_dump        = '-dump'
    arg_elf         = '-elf'
    arg_o           = '-o'

    args            = [arg_dump, arg_elf, arg_o]
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
    fonts           = QFontDatabase().families()
    v_font          = tab.get(arg_font)
    v_size          = tab.get(arg_size)
    v_mode          = tab.get(arg_mode)
    v_w             = tab.get(arg_w)
    v_h             = tab.get(arg_h)
    v_dump          = tab.get(arg_dump)
    v_elf           = tab.get(arg_elf)
    v_o             = tab.get(arg_o)
    error_param     = False

    def parse_int_param(typ, val):
        if  re.match(r'\d+', val):
            return int(val)
        else:
            error_param = True
            print("error param '%s' for '%s', please assign it by integer" % (val, typ))
            return -1


    if  v_font not in fonts:
        error_param = True
        print("font '%s' not available" % v_font)

    v_size          = parse_int_param(arg_size, v_size)

    if  re.match(r'0|1|2|3', v_mode):
        v_mode = int(v_mode)
    else:
        error_param = True
        print("error param '%s' for '%s', please assign it in range [0, 1, 2, 3]" % (v_size, arg_size))

    v_w             = parse_int_param(arg_w, v_w)
    v_h             = parse_int_param(arg_h, v_h)

    if  error_param:
        return

    cmd             = '%s -j .rodata -s %s' % (v_dump, v_elf)
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
    utf16_list      = fetch_utf8(vals)
    create_file(
        font=v_font, 
        font_size=v_size, 
        cell_width=v_w, 
        cell_height=v_h,
        unicodes=utf16_list,
        mode=v_mode,
        output=v_o
    )

app = QApplication(sys.argv)
generate(sys.argv[1:])
