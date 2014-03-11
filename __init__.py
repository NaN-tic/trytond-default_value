# This file is part of the default_value module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from .default_value import *


def register():
    Pool.register(
        DefaultValue,
        module='default_value', type_='model')
