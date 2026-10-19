# dash-nand: källor och byggbeskrivning för installationen i plattans inbyggda minne (NAND)

Som v3 (se `_gamla-v3/dash-nand-kalla-v3.tar.gz`), med de här ändringarna – alla provade på dash som nu kör från NAND:

## U-Boot 2024.01
- Patch 0001 (A23-kompatibel i sunxi_nand) + **0002**: kompatibeln borttagen igen (U-Boots egen NAND-drivrutin hängde
  före skärmen) och kommandot `dashnload` (`board/sunxi/dash_nload.c`, kopia av SPL:s NAND-läsare).
- `uboot-q8-a33-dashnand-final.config`: startkommandot använder `dashnload`; bootargs
  `console=ttyS0,115200 console=tty1 ubi.mtd=ubi root=ubi0:rootfs rootfstype=ubifs rootwait rw panic=10 consoleblank=0 loglevel=4`.
- Startfilen (SPL) oförändrad: md5 228164608fb9…

## Linux 6.12.82-dashnand
- Patchar 0001–0004 (0003: pekskärmen som i dashs egen dtb; 0004: bara två avbrott på pio – tre låser den här kärnan).
- Config: `CONFIG_EXTRA_FIRMWARE="silead/gsl2681-b482-q8.fw"` (pekskärmens firmware inbyggd, katalogen `dash-fw/` i trädet),
  `FB_SIMPLE=y`, `DRM_SIMPLEDRM` av. `make LOCALVERSION= DTC_FLAGS=-@ zImage allwinner/sun8i-a33-q8-tablet-dashnand.dtb`.
- Enhetsträdet på NAND = dashnand.dtb + r5:s `dash-battery.dtbo` (fdtoverlay).

## Rotfilsystemet
- `dash-firstboot`: `read_sid()` läser högst 64 byte per nvmem-enhet (MTD-partitionerna är också nvmem; 4 GB lästes -> OOM).
- Panelen: GitHub `blobba79/dash-panel` gren `release` (18f4ceb, version 1.4), uppackad som `dash-update` gör
  (rättigheter 0700/0600, `VERSION.json` med `tree_sha256`), `/etc/dash-update/config.ini` `ref = release`.
- Spelen ur `main` (2fa0165) i `/var/lib/dash-panel/games/`: blockpussel, sudoku, patians (harpan.py är trasig i repot, utelämnad).
- `simplefb.ko` borttagen (inbyggd), `modules.builtin*` från kärnbygget, `depmod`.
- `/usr/local/share/dash-nand/`: `boot-uppdatera.py` m.fl. (byta U-Boot från det körande NAND-systemet).
- `mkfs.ubifs -m 8192 -e 1032192 -c 4000 -x zstd -F`, `ubinize -p 1MiB -m 8192 -s 8192 -O 8192 ubinize.cfg`.

## Installationsprogrammet
- Läser dåliga block före `nandbbm` (≤80 = fabriksmarkeringar, hoppas över; fler = Androids NFTL-data, allt raderas),
  raderar UBI-området självt, laddar om `nandbbm restore=1` före ubiformat. Chip-id som nollor -> namnet ur Wi-Fi-adressen.

## Installationskortet
- r5:s första 16 MiB + ext4 (`mke2fs -t ext4 -b 4096 -O ^orphan_file,^metadata_csum_seed -U 4d04797f-… -L armbi_root
  -E hash_seed=449fc412-… -N 73728 -m 1 -d instroot … 294912`, `tune2fs -o journal_data_writeback,user_xattr,acl -e continue`).
