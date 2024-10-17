# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import base64
import logging
import re

_logger = logging.getLogger(__name__)


class SaleSubchapter(models.Model):
    _name = 'sale.subchapter'
    _description = 'Subchapter of sale'

    name = fields.Char(string='Nombre', required=True)
    bc3_subchapter_id = fields.Char(string="Bc3 Import Id")
    chapter_id = fields.Many2one('sale.capitulo', string='Capitulo')
    line_ids = fields.One2many(comodel_name='sale.order.line', inverse_name='order_id', string="Order Lines")