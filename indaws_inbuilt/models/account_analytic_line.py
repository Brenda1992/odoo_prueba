# -*- coding: utf-8 -*-

from odoo import fields, models, api

class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'


    indaws_analytic_line = fields.Boolean('indaws_analytic_line', default=False)
    po_task_id = fields.Many2one('project.task', string="PO Task")
    extra_hour_id = fields.Many2one('product.template', string='Hora extra', domain="[('overtime', '=', True)]")
    capitulo_analytic_id = fields.Many2one('account.analytic.line', string='Capitulo_Timesheet')
    cost_type = fields.Many2one('cost.classification', string='Tipo de coste', compute='_compute_cost_type', store=True)

    @api.depends('general_account_id', 'project_id', 'employee_id', 'name', 'product_id')
    def _compute_cost_type(self):
        for record in self:
            type_id = None
            obj_cost_classification = self.env['cost.classification']
            # si hay cuenta contable, entonces buscamos el tipo de obra
            if record.general_account_id:
                if record.general_account_id.account_type == 'expense':
                    tipo = obj_cost_classification.search([('account_ids', 'in', record.general_account_id.id)], limit=1)
                    if tipo:
                        type_id = tipo.id
                    else:
                        tipo = obj_cost_classification.search([('is_other_costs', '=', True)], limit=1)
                        if tipo:
                            type_id = tipo.id
            # si no hay cuenta, contable, vemos si es parte de horas
            elif record.project_id and record.employee_id:
                if record.employee_id.cost_type:
                    type_id = record.employee_id.cost_type.id
                else:
                    tipo = obj_cost_classification.search([('is_part_hours', '=', True)], limit=1)
                    if tipo:
                        type_id = tipo.id
            # En caso contrario se toma el Tipo de coste del producto
            else:
                if record.product_id and record.product_id.product_type_unit:
                    type_id = record.product_id.product_type_unit.id
            record.write({'cost_type': type_id})


    def _timesheet_postprocess(self, values):
        """ Hook to update record one by one according to the values of a `write` or a `create`. """
        if 'indaws_analytic_line' not in values or ('indaws_analytic_line' in values and not values.get('indaws_analytic_line')):
            sudo_self = self.sudo()  # this creates only one env for all operation that required sudo() in `_timesheet_postprocess_values`override
            values_to_write = self._timesheet_postprocess_values(values)
            for timesheet in sudo_self:
                if values_to_write[timesheet.id]:
                    timesheet.write(values_to_write[timesheet.id])
        return values

    @api.model_create_multi
    def create(self, vals):
        for val in vals:
            if val.get('task_id', False) and not val.get('po_task_id', False):
                val['po_task_id'] = val['task_id']
                
        res = super().create(vals)
        for item in res:
            if item.task_id and item.task_id.child_ids and item.project_id and not item.capitulo_analytic_id:
                capitulo_id = self.env['sale.capitulo'].search([('task_id', '=', item.task_id.id)], limit=1)
                if capitulo_id:
                    for line in capitulo_id.line_ids:
                        if line.task_id:
                            percent = line.cost_subtotal / capitulo_id.cost_price if capitulo_id.cost_price else 0
                            unit_amount = item.unit_amount * percent
                            item.copy({
                                'task_id': line.task_id.id,
                                'capitulo_analytic_id': item.id,
                                'unit_amount': unit_amount,
                                'validated': True
                            })
        return res

    def write(self, vals):
        if vals.get('task_id', False) and not vals.get('po_task_id', False):
            vals['po_task_id'] = vals['task_id']

        if 'extra_hour_id' in vals:
            if vals.get('extra_hour_id'):
                vals['amount'] = self.calculate_amount(vals.get('extra_hour_id'))
            else:
                vals['amount'] = (round(self.employee_id.hourly_cost, 2) * self.unit_amount) * -1 if self.employee_id else 0.0
        else:
            if 'amount' in vals:
                if self.extra_hour_id:
                    vals['amount'] = self.calculate_amount()

        previous_task_id = None
        if 'task_id' in vals:
            previous_task_id = self.task_id

        res = super(AccountAnalyticLine, self).write(vals)
        if 'unit_amount' in vals or 'task_id' in vals:
            capitulo_id = self.env['sale.capitulo'].search([('task_id', '=', self.task_id.id)], limit=1)
            if capitulo_id:
                for line in capitulo_id.line_ids:
                    percent = line.cost_subtotal / capitulo_id.cost_price if capitulo_id.cost_price else 0
                    unit_amount = self.unit_amount * percent
                    if line.task_id and line.task_id.timesheet_ids and line.task_id.timesheet_ids.filtered(lambda x: x.capitulo_analytic_id):
                        line.task_id.timesheet_ids.filtered(lambda x: x.capitulo_analytic_id).write({
                            'unit_amount': unit_amount,
                            'validated': True
                        })
                    elif line.task_id and (line.task_id.timesheet_ids and not line.task_id.timesheet_ids.filtered(
                            lambda x: x.capitulo_analytic_id) or not line.task_id.timesheet_ids):
                        self.copy({
                            'task_id': line.task_id.id,
                            'capitulo_analytic_id': self.id,
                            'unit_amount': unit_amount,
                            'validated': True
                        })
        if 'task_id' in vals:
            capitulo_previous_id = None
            if previous_task_id:
                capitulo_previous_id = self.env['sale.capitulo'].search([('task_id', '=', previous_task_id.id)], limit=1)
            capitulo_id = self.env['sale.capitulo'].search([('task_id', '=', vals.get('task_id', False))], limit=1)

            if capitulo_previous_id and capitulo_previous_id != capitulo_id:
                for line in capitulo_previous_id.line_ids:
                    line.task_id.timesheet_ids.filtered(lambda x: x.capitulo_analytic_id == self).sudo().unlink()
        return res


    def calculate_amount(self, hour=None):
        extra_hour_id = self.env['product.template'].search([('id', '=', int(hour))]) if hour else None
        if self.extra_hour_id or extra_hour_id:
            if self.employee_id and self.employee_id.employee_overtime_ids:
                extra_hour = self.employee_id.employee_overtime_ids.filtered(lambda x: x.product_id == (extra_hour_id if extra_hour_id else self.extra_hour_id))
                if extra_hour and extra_hour[-1].cost > 0:
                    return (round(extra_hour[-1].cost, 2) * self.unit_amount) * -1
                else:
                    return self.get_amount(extra_hour_id) if extra_hour_id else self.get_amount()
            else:
                return self.get_amount(extra_hour_id) if extra_hour_id else self.get_amount()
        else:
            return (round(self.employee_id.hourly_cost, 2) * self.unit_amount) * -100.00


    def get_amount(self, extra_hour_id=None):#TODO TRAIDO de indaws_employee_overtime_updates
        if extra_hour_id and extra_hour_id.standard_price > 0:
            return (round(extra_hour_id.standard_price, 2) * self.unit_amount) * -1
        elif self.extra_hour_id and self.extra_hour_id.standard_price > 0:
            return (round(self.extra_hour_id.standard_price, 2) * self.unit_amount) * -1
        else:
            return (round(self.employee_id.hourly_cost, 2) * self.unit_amount) * -1

    def unlink(self):
        for anlytic_line in self:
            self.env['account.analytic.line'].search([('capitulo_analytic_id', '=', anlytic_line.id)]).unlink()
        return super(AccountAnalyticLine, self).unlink()

    def get_timesheet_values(self):
        qty = abs(self.unit_amount)
        cost_subtotal = abs(self.amount)
        cost_unit = round(cost_subtotal / qty, 2) if qty else 0.00

        if self.extra_hour_id and self.extra_hour_id.id in self.employee_id.employee_overtime_ids.mapped('product_id').ids:
            price_unit = self.employee_id.employee_overtime_ids.filtered(lambda r: r.product_id != self.extra_hour_id).sale_price
        elif self.extra_hour_id:
            price_unit = self.extra_hour_id.list_price
        elif self.employee_id.product_template_id:
            price_unit = self.employee_id.product_template_id.list_price
        else:
            price_unit = self.employee_id.timesheet_sale

        price_subtotal = price_unit * qty
        return {
            'qty': qty,
            'cost_unit': cost_unit,
            'cost_subtotal': cost_subtotal,
            'price_unit': price_unit,
            'price_subtotal': price_subtotal,
        }
