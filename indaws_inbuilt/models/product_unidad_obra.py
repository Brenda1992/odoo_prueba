# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProductUnidadObra(models.Model):
    _name = 'product.unidad.obra'
    _description = 'Unidad de Obra'

    product_id = fields.Many2one('product.product', string='Producto', required=True)
    comment = fields.Text(string='Notas')
    product_tmpl_id = fields.Many2one('product.template', string='Product Template')
    quantity = fields.Float(string='Cantidad', default=1.0)
    uom_id = fields.Many2one('uom.uom', string='UdM')
    currency_id = fields.Many2one(related='product_tmpl_id.currency_id', string='Currency')
    price_unit = fields.Float(string='Precio unitario', currency_field='currency_id', readonly=False)
    cost_unit = fields.Monetary(string='Coste unitario', currency_field='currency_id', group_operator=False)
    price_subtotal = fields.Float(string='Precio de Venta', compute='_compute_price_subtotal', store=True)
    cost_subtotal = fields.Float(string='Precio de coste', compute='_compute_cost_subtotal', store=True)
    incremento = fields.Float(string='% incremento', readonly=False, store=True)
    product_type_calc = fields.Many2one(
        'cost.classification',
        related='product_id.product_tmpl_id.product_type_unit',
        string='Tipo de Producto'
    )
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id.id
            if self.product_id.computed_cost != 0:
                self.cost_unit = self.product_id.computed_cost
            else:
                self.cost_unit = self.product_id.standard_price
            if self.incremento == 0:
                self.price_unit = self.product_id.lst_price

    @api.depends('price_unit', 'quantity')
    def _compute_price_subtotal(self):
        for record in self:
            record.price_subtotal = 0
            if record.price_unit and record.quantity and record.product_id:
                record.price_subtotal = record.price_unit * record.quantity

    @api.depends('cost_unit', 'quantity')
    def _compute_cost_subtotal(self):
        for record in self:
            record.cost_subtotal = 0
            if record.cost_unit and record.quantity and record.product_id:
                record.cost_subtotal = record.cost_unit * record.quantity
    @api.onchange('incremento', 'cost_unit')
    def onchange_incremento(self):
        for rec in self:
            if rec.incremento:
                rec.price_unit = rec.cost_unit * (1 + (rec.incremento / 100))

    @api.onchange('price_unit', 'cost_unit')
    def onchange_price_unit_cost_unit(self):
        for record in self:
            if record.product_id and record.cost_unit != 0:
                record.incremento = 100 * ((record.price_unit / record.cost_unit) - 1)
