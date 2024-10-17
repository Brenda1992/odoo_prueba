# -*- coding: utf-8 -*-

from odoo import models, fields, api


class SaleUnidadObra(models.Model):
    _name = 'sale.unidad.obra'
    _description = 'Unidad de Obra'

    product_id = fields.Many2one('product.product', string='Producto', required=True)
    comment = fields.Text(string='Notas')
    order_line_id = fields.Many2one('sale.order.line', string='Linea de pedido', ondelete='cascade', copy=False)
    quantity = fields.Float(string='Cantidad', default=1.0, digits=(16, 3))
    uom_id = fields.Many2one('uom.uom', string='UdM')
    currency_id = fields.Many2one(related='order_line_id.currency_id', string='Currency')
    price_unit = fields.Float(string='Precio unitario', readonly=False, digits='Product Price')
    cost_unit = fields.Float(string='Coste unitario', group_operator=False, digits='Product Price')
    price_subtotal = fields.Monetary(string='Precio de Venta', compute='_compute_price_subtotal', store=True, digits='Product Price')
    cost_subtotal = fields.Monetary(string='Precio de coste', compute='_compute_cost_subtotal', store=True, digits='Product Price')
    capitulo_id = fields.Many2one('sale.capitulo', related='order_line_id.capitulo_id', string='Capitulo', store=True, required=False)
    incremento = fields.Float(string='% incremento', readonly=False, store=True)
    order_id = fields.Many2one('sale.order', related='order_line_id.order_id', string='Order', store=True, copy=False)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    product_type_calc = fields.Many2one(
        'cost.classification',
        related='product_id.product_tmpl_id.product_type_unit',
        string='Tipo de Producto'
    )
    traspaso_id = fields.One2many(comodel_name='project.task.material', inverse_name='sale_unidad_obra_id')

    @api.onchange('product_id')
    def onchange_product_id(self):
        # if self.product_id and self.product_id.product_type_calc == 'mano_de_obra' or self.product_id.product_type_calc == 'gastos_generales':
        if self.product_id and self.product_id.product_type_unit.is_part_hours or self.product_id.product_type_unit.is_other_costs:
            self.price_unit = self.product_id.lst_price
            self.uom_id = self.product_id.uom_id.id
            self.cost_unit = self.product_id.standard_price
        elif self.product_id:
            self.incremento=self.order_line_id.incremento
            self.uom_id = self.product_id.uom_id.id
            self.cost_unit = self.product_id.standard_price
        if self.incremento == 0:
            self.price_unit = self.product_id.lst_price

    @api.depends('price_unit', 'quantity')
    def _compute_price_subtotal(self):
        for record in self:
            record.price_subtotal = 0
            if record.price_unit and record.quantity and record.product_id:
                record.price_subtotal = record.price_unit * record.quantity
            else:
                record.price_subtotal = 0

    @api.depends('cost_unit', 'quantity')
    def _compute_cost_subtotal(self):
        for record in self:
            record.cost_subtotal = 0
            if record.cost_unit and record.quantity and record.product_id:
                record.cost_subtotal = record.cost_unit * record.quantity
            else:
                record.cost_subtotal = 0

    @api.onchange('incremento', 'cost_unit')
    def onchange_incremento(self):
        for rec in self:
            if rec.incremento:
                rec.price_unit = rec.cost_unit * (1 + (rec.incremento / 100))

    @api.onchange('price_unit', 'cost_unit')
    def onchange_price_unit_cost_unit(self):
        for record in self:
            if record.product_id:
                if record.cost_unit != 0:
                    old_incremento = record.incremento
                    new_incremento = 100 * ((record.price_unit / record.cost_unit) - 1)
                    if abs(old_incremento - new_incremento) > 0.02:
                        record.incremento = new_incremento

    @api.model_create_multi
    def create(self, values):
        res = super(SaleUnidadObra, self).create(values)
        for item in res:
            if item.order_id.project_id and item.product_type_calc.is_materials and item.id in item.order_id.get_unidades_id_to_purchase().ids:
                material_id = self.env['project.task.material'].search([
                    ('sale_unidad_obra_id', '=', item.id)
                ])
                if not material_id:
                    qty = item.order_line_id.product_uom_qty * item.quantity
                    self.env['project.task.material'].create({
                        'project_id': item.order_id.project_id.id,
                        'product_id': item.product_id.id,
                        'task_id': item.order_line_id.task_id and item.order_line_id.task_id.id or False,
                        'quantity': qty,
                        'cost': item.cost_unit,
                        'price_unit': item.price_unit,
                        'sale_unidad_obra_id': item.id,
                        'sale_id': item.order_id.id,
                    })
        return res