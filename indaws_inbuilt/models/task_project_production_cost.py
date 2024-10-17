# -*- coding: utf-8 -*-

from odoo import models, fields, api


class TaskProjectProductionCost(models.Model):
    _name = 'task.project.production.cost'
    _description = 'task project production cost'

    name = fields.Char(string='Nombre')
    coste = fields.Monetary(string='Coste', currency_field='currency_id')
    currency_id = fields.Many2one("res.currency", "Currency", readonly=True)
    task_id = fields.Many2one('project.task', string='Project Task', ondelete="cascade")
    quantity = fields.Float('Cantidad')
