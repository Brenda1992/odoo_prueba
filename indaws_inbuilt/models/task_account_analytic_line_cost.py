# -*- coding: utf-8 -*-

from odoo import models, fields, api


class TaskAccountAnalyticLineCost(models.Model):
    _name = 'task.account.analytic.line.cost'
    _description = 'task account analytic line.cost'

    name = fields.Char(string='Nombre')
    coste = fields.Monetary(string='Coste', currency_field='currency_id')
    currency_id = fields.Many2one("res.currency", "Currency", readonly=True)
    task_id = fields.Many2one('project.task', string='Project Task', ondelete="cascade")
    quantity = fields.Float('Cantidad')
