#!/usr/bin/python3
# Byter U-Boot (och skriver om SPL) i NAND-startområdet från det körande NAND-systemet.
# Startområdet är skrivskyddat i drift; nandbbm.ko unlock=1 gör det skrivbart till nästa omstart.
import os, sys, hashlib, fcntl, struct, subprocess, importlib.util
D = os.path.dirname(os.path.abspath(__file__))
s = importlib.util.spec_from_file_location('i', D + '/inst.py'); i = importlib.util.module_from_spec(s); s.loader.exec_module(i)
ub = open(sys.argv[1], 'rb').read(); spl = open(D + '/sunxi-spl-with-ecc.bin', 'rb').read()
print('u-boot md5', hashlib.md5(ub).hexdigest(), 'spl md5', hashlib.md5(spl).hexdigest())
parts = i.mtd_by_name(); print(parts)
bad = i.bad_list(parts['boot'])
if bad:
    sys.exit('startområdet har block som räknas som dåliga %s; avbryter' % bad)
if not os.path.exists('/sys/module/nandbbm'):
    subprocess.run(['insmod', D + '/nandbbm-dashnand.ko', 'name=boot', 'unlock=1', 'restore=1'], check=True)
fd = i.mtd_open(parts['boot'])
b = i.erase_all(fd, int(i.sysattr(parts['boot'], 'size')), 'boot')
if b:
    sys.exit('boot: block gick inte att radera: %s' % b)
w = i.write_boot(fd, spl, ub); os.close(fd)
print('KLART: SPL + U-Boot skrivna och kontrollerade, högst %d felbitar i SPL' % w)
