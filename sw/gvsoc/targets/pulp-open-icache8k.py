#
# Target gvsoc "pulp-open-icache8k": thi nghiem lop 4, shared I-cache 8 KiB.
#
# Dung: gvsoc --target-dir=<repo>/sw/gvsoc/targets --target=pulp-open-icache8k ...
#
# Khong sua ban goc trong ~/gvsoc: chi thay file cau hinh cluster mac dinh
# cua Pulp_open bang pulp_open_icache8k/cluster.json. Khac biet so voi goc:
#   - icache/config/l1/nb_sets_bits 5 -> 6. Shared I-cache co nb_l1_banks=2,
#     nen dung luong tu 2 x 2 KiB = 4 KiB (bang RTL) len 2 x 4 KiB = 8 KiB.
#     Day la cau hinh KHAC RTL, dung de thay tac dong cua kich thuoc cache
#     (sw/gvsoc/icache_sweep).
#

import os
import pulp.chips.pulp_open.pulp_open as pulp_open_mod
from pulp.chips.pulp_open.pulp_open_board import Pulp_open_board
import gvsoc.runner as gvsoc

_CLUSTER_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'pulp_open_icache8k', 'cluster.json')

_orig_init = pulp_open_mod.Pulp_open.__init__

def _init(self, parent, name, attr, parser, **kwargs):
    kwargs.setdefault('cluster_config_file', _CLUSTER_JSON)
    _orig_init(self, parent, name, attr, parser, **kwargs)

pulp_open_mod.Pulp_open.__init__ = _init


class Target(gvsoc.Target):

    gapy_description = "Pulp-open, shared I-cache 8 KiB (thi nghiem, khac RTL)"
    model = Pulp_open_board
    name = "pulp-open-icache8k"

    def __init__(self, parser, options=None, name=None):
        super(Target, self).__init__(parser, options,
            model=Pulp_open_board, name=name)
