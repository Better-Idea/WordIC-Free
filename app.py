import io
import sys
import subprocess

arg_dump = '-dump'
arg_bin  = '-bin'
arg_word = '-word'
arg_o    = '-o'
args     = [arg_dump, arg_bin, arg_word, arg_o]

def main():
    tab = dict()

    for i in sys.argv:
        [k, v] = i.split('=')
        tab.setdefault(k, v)

    miss_arg = False

    for arg in args:
        if  arg not in tab:
            print('miss param', arg)
            miss_arg = True

    if  miss_arg:
        return

    dump = tab.get(arg_dump)
    bin  = tab.get(arg_bin)
    word = tab.get(arg_word)
    o    = tab.get(arg_o)
    cmd  = '%s -j .rodata -s %s' % (dump, bin)
    sub  = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    sub.wait()
    r    = str(sub.communicate()[0], 'utf-8').split('\n')
    vals = []
    
    for line in r[4:]:
        for hex_int in line.split(' ')[2:5]:
            vals += int(hex_int, 16).to_bytes(length=4, byteorder='big')

    more  = 0
    full  = 0
    lut   = []
    line  = []

    for byte in vals:
        if  byte == 0:
            line.append(0)
            lut.append(line)
            line   = []
            continue
        if  more > 1:
            more  -= 1
            full   = full << 8 | byte
            continue
        elif more == 1:
            line.append(full)
            more   = 0
            full   = 0

        mask = byte & 0xf8
        full = byte

        if  mask  <= 0x78:
            line.append(byte)
        elif mask  >= 0xf0:
            # more   = 4 5 6
            raise 'not support'
        elif mask >= 0xe0:
            more   = 3
        elif mask >= 0xc0:
            more   = 2

    # to be continue
    print(lut)

main()
