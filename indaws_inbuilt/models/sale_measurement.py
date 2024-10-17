# -*- coding: utf-8 -*-

from odoo import models, fields, api


class SaleUnidadObra(models.Model):
    _name = 'sale.measurement'
    _description = 'Sale Measurement'
    _rec_name = 'description'


    description = fields.Char('Descripción')
    units = fields.Float('Uds')
    length = fields.Float('Longitud', digits=(16, 3))
    width = fields.Float('Anchura', digits=(16, 3))
    height = fields.Float('Altura', digits=(16, 3))
    partial = fields.Float('Parciales', digits=(16, 3), compute='_compute_partial')
    order_line_id = fields.Many2one('sale.order.line', string='Linea de pedido', ondelete='cascade', copy=False)


    @api.depends('units', 'length', 'width', 'height')
    def _compute_partial(self):
        for item in self:
            dimensions = [item.length, item.width, item.height]
            nonzero_dimensions = [dim for dim in dimensions if dim > 0]
            if len(nonzero_dimensions) == 3:
                item.partial = item.units * item.length * item.width * item.height
            elif len(nonzero_dimensions) == 2:
                item.partial = item.units * nonzero_dimensions[0] * nonzero_dimensions[1]
            elif len(nonzero_dimensions) == 1:
                item.partial = item.units * nonzero_dimensions[0]
            else:
                item.partial = item.units

