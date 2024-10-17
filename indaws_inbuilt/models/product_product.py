# -*- coding: utf-8 -*-

from odoo import models, fields, api



class ProductProduct(models.Model):
    _inherit = 'product.product'

    def action_update_price(self):
        for product in self:
            product.list_price = product.computed_sale_price
            product.standard_price = product.computed_cost