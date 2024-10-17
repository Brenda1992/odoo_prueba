# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class CostClassification(models.Model):
    _name = 'cost.classification'
    _description = 'Cost classification'

    name = fields.Char('Descripción')
    account_ids = fields.Many2many('account.account', string='Cuentas contables')
    default_purchase_account = fields.Many2one('account.account', string='Cuenta de compra por defecto')
    default_sales_account = fields.Many2one('account.account', string='Cuenta de venta por defecto')
    is_part_hours = fields.Boolean('Es parte de horas')
    is_materials = fields.Boolean('Es materiales')
    is_subcontract = fields.Boolean('Es subcontract')
    is_other_costs = fields.Boolean('Otros')
