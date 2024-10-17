# -*- coding: utf-8 -*-

from odoo import models, fields, api


class SaleLineUnidadCost(models.Model):
    _name = 'sale.line.unidad.cost'
    _description = 'sale line unidad cost'


    name = fields.Char(string='Nombre')
    coste = fields.Monetary(string='Coste', currency_field='currency_id')
    currency_id = fields.Many2one("res.currency", "Currency", readonly=True)
    sale_order_id = fields.Many2one('sale.order', string='sale order', ondelete="cascade")
    quantity = fields.Float('Cantidad')