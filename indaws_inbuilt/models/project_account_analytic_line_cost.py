# -*- coding: utf-8 -*-

from odoo import models, fields, api


class TaskProjectProductionCost(models.Model):
    _name = 'project.account.analytic.line.cost'
    _description = 'project account analytic line cost'

    name = fields.Char(string='Nombre')
    coste = fields.Monetary(string='Coste', currency_field='currency_id')
    currency_id = fields.Many2one("res.currency", "Currency", readonly=True)
    project_id = fields.Many2one('project.project', string='Project', ondelete="cascade")
    quantity = fields.Float('Cantidad')