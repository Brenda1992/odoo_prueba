# -*- coding: utf-8 -*-

from odoo import fields, models


class Employee(models.Model):
    _inherit = 'hr.employee'

    employee_overtime_ids = fields.One2many('hr.employee.extra.hour', 'employee_id', string='Horas extras de empleado')
    timesheet_sale = fields.Monetary(string="Precio Venta Hora", currency_field='currency_id', groups="hr.group_hr_user")
    product_template_id = fields.Many2one('product.template', string="Producto", currency_field='currency_id', groups="hr.group_hr_user")
    cost_type = fields.Many2one('cost.classification', string="Tipo de ud de obra")
