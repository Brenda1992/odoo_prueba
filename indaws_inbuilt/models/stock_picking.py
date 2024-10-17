# -*- coding: utf-8 -*-

from odoo import models, fields


class Stock_Picking_Inherit(models.Model):
    _inherit = 'stock.picking'

    project_id = fields.Many2one('project.project', 'Project')