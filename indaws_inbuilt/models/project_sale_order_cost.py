# -*- coding: utf-8 -*-

from odoo import models, fields, api


class TaskProjectProductionCost(models.Model):
    _name = 'project.sale.order.cost'
    _description = 'project sale order cost'

    name = fields.Char(string='Nombre')
    coste = fields.Monetary(string='Coste', currency_field='currency_id')
    currency_id = fields.Many2one("res.currency", "Currency", readonly=True)
    project_id = fields.Many2one('project.project', string='Project', ondelete="cascade")
    quantity = fields.Float('Cantidad')