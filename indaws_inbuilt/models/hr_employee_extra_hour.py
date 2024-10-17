# -*- coding: utf-8 -*-

from odoo import models, fields


class HrEmployeeExtraHour(models.Model):
    _name = 'hr.employee.extra.hour'
    _description = 'Hr Employee Extra Hour'

    employee_id = fields.Many2one('hr.employee', string='Empleado')
    product_id = fields.Many2one('product.template', string='Hora', domain="[('overtime', '=', True)]")
    cost = fields.Float('Coste')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    sale_price = fields.Float(string="Precio Venta")