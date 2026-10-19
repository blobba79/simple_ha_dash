// Hjalpmodul for dash-nand-installationen: later Linux bortse fran "daliga block"-markeringar,
// eftersom Allwinners NFTL-data i OOB ser ut som daliga block. Galler tills omstart.
// name = valfri MTD-enhet pa kretsen (en partition gar bra; modulen gar alltid till sjalva kretsen).
#include <linux/module.h>
#include <linux/mtd/mtd.h>
#include <linux/mtd/rawnand.h>

static char *name = "boot";
module_param(name, charp, 0444);
static int restore;
module_param(restore, int, 0444);	/* 1 = sla pa BBM-kontrollen igen (lasning av markeringen direkt, utan tabell) */
static int unlock;
module_param(unlock, int, 0444);	/* 1 = gor partitionen name skrivbar (startomradet ar skrivskyddat i NAND-systemet) */

static int __init nandbbm_init(void)
{
	struct mtd_info *mtd = get_mtd_device_nm(name);
	struct mtd_info *master;
	struct nand_chip *chip;

	if (IS_ERR(mtd)) {
		pr_err("nandbbm: hittar inte %s\n", name);
		return PTR_ERR(mtd);
	}
	if (unlock) {
		mtd->flags |= MTD_WRITEABLE;
		pr_info("nandbbm: %s skrivbar till omstart\n", mtd->name);
	}
	master = mtd_get_master(mtd);
	chip = mtd_to_nand(master);
	if (restore) {
		/* efter att installationen raderat kretsen: markeringarna stammer igen, las dem direkt */
		chip->options &= ~NAND_NO_BBM_QUIRK;
		pr_info("nandbbm: %s (krets %s) options=0x%x bbt=%p -> BBM-kontroll pa igen\n",
			mtd->name, master->name, chip->options, chip->bbt);
		put_mtd_device(mtd);
		return 0;
	}
	pr_info("nandbbm: %s (krets %s) options=0x%x bbt=%p -> ignorerar BBM\n",
		mtd->name, master->name, chip->options, chip->bbt);
	chip->options |= NAND_NO_BBM_QUIRK;
	chip->bbt = NULL;
	put_mtd_device(mtd);
	return 0;
}

static void __exit nandbbm_exit(void) { }

module_init(nandbbm_init);
module_exit(nandbbm_exit);
MODULE_LICENSE("GPL");
