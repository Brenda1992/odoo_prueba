# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    product_type_calc = fields.Selection([
        ('mano_de_obra', 'Mano de Obra'),
        ('materials', 'Materiales'),
        ('maquinaria', 'Maquinaria'),
        ('gastos_generales', 'Otros costes')
    ],
        string='Tipo unidad de obra Anterior'
    )
    product_type_unit = fields.Many2one('cost.classification', string='Tipo unidad de obra')
    price_type = fields.Selection([
        ('manual', 'Manual'),
        ('automático', 'Automático')
    ],
        default='manual',
        string='Cálculo Precio',
        help='Manual: En el Presupuesto el precio del producto será el establecido en la Ficha \n '
             'Automático: En el Presupuesto el precio del producto será la suma del precio de las unidades de Obra'
    )

    ubicanion = fields.Char(string='Ubicación')
    unidades_ids = fields.One2many('product.unidad.obra', 'product_tmpl_id', string='Unidades de Obra', copy=True)
    computed_cost = fields.Float(string='Coste calculado', compute="_compute_unidased_cost")
    computed_sale_price = fields.Float(string="Precio calculado", compute="_compute_unidased_cost")
    computed_margin = fields.Float(string="% Margen", compute="_compute_unidased_cost")
    show_update_btn = fields.Boolean(compute="_compute_show_update_btn")
    overtime = fields.Boolean('Horas extras')

    @api.depends('unidades_ids')
    def _compute_unidased_cost(self):
        for rec in self:
            rec.computed_cost = 0
            rec.computed_sale_price = 0
            rec.computed_margin = 0
            if rec.unidades_ids:
                rec.computed_cost = sum([line.cost_subtotal for line in rec.unidades_ids])
                rec.computed_sale_price = sum([line.price_subtotal for line in rec.unidades_ids])
                if rec.computed_sale_price:
                    rec.computed_margin = ((rec.computed_sale_price - rec.computed_cost) / rec.computed_sale_price) * 100

    def action_update_price(self):
        for product in self:
            product.list_price = product.computed_sale_price
            product.standard_price = product.computed_cost

    @api.depends('computed_sale_price', 'list_price')
    def _compute_show_update_btn(self):
        for rec in self:
            rec.show_update_btn = False
            if rec.computed_sale_price != rec.list_price or rec.computed_cost != rec.standard_price:
                rec.show_update_btn = True
