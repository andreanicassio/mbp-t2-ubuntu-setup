#!/bin/bash
# Re-enable the low-volume t2bce_vhci debug sites (control transfers, queue pause/reset/abort). Lost on reboot.
sudo bash -c 'C=/proc/dynamic_debug/control; for l in 149 171 190 204 319 390 422 443 567 574 587 595 606 611; do echo "file drivers/staging/t2bce/t2bce_vhci/transfer.c line $l +pt" > $C; done; for l in 878 924; do echo "file drivers/staging/t2bce/t2bce_vhci/vhci.c line $l +pt" > $C; done; echo "enabled: $(grep -c "t2bce_vhci.*=pt" $C)"'
