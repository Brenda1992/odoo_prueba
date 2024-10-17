# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import math
from odoo.exceptions import UserError


class Task(models.Model):
    _inherit = 'project.task'

    material_ids = fields.One2many('project.task.material', 'task_id', string='Materiales')
    coste_horas = fields.Float(string='Coste de horas', compute='_compute_coste_horas')
    coste_materiales = fields.Float(string='Coste de materiales', compute='_compute_coste_materiales')
    coste_total = fields.Float(string='Coste Total', compute='_compute_coste_total')
    coste_materiales_capitulo = fields.Float(
        string='Coste de materiales Capitulo',
        compute='_compute_coste_materiales_capitulo'
    )
    coste_materiales_capitulo_pct = fields.Float(
        string='percent Coste de materiales Capitulo',
        compute='_compute_coste_materiales_capitulo'
    )
    invoice_id = fields.Many2one('account.move', string="Facturas")
    show_fectura_btn = fields.Boolean(compute='_compute_show_fectura_btn')
    invoice_status = fields.Selection([
        ('invoiced', 'Fully Invoiced'),
        ('to invoice', 'To Invoice'),
        ('no', 'Nothing to Invoice')],
        string='Invoice Status', compute='_get_invoice_status', store=True)
    project_production_ids = fields.One2many(
        'project.production',
        'task_id',
        string='Project Production'
    )
    forecast_costs_ids = fields.One2many(
        'task.project.production.cost',
        'task_id',
        string='Costes directos previstos',
        compute='_compute_forecast_costs_ids'
    )
    cost_forecast = fields.Float('Coste directo previsto', compute='_compute_forecast_costs_ids')
    real_costs_ids = fields.One2many(
        'task.account.analytic.line.cost',
        'task_id',
        string='Costes directos reales',
        compute='_compute_real_costs_ids'
    )
    cost_real = fields.Float('Coste directo real', compute='_compute_real_costs_ids')
    cost_deviation = fields.Float('Desviación de costes', compute='_compute_cost_deviation')
    planned_hours_task = fields.Float('Horas planeadas', compute='_compute_planned_hours')
    hours_left = fields.Float('Horas restantes', compute='_compute_hours_left')
    planning_count = fields.Integer(string="Invoice Count", compute='_compute_planning_count')

    def _search_model_information(self, model, field_name, name, value):
        line = self.env[model].search([
            (field_name, '=', self.id),
            ('name', '=', name)
        ], limit=1)
        if line:
            line.coste = value.get('coste')
            line.quantity = value.get('qty')
            cost_id = line.id
        else:
            cost_id = self.env[model].create([{
                'name': name,
                'coste': value.get('coste'),
                'quantity': value.get('qty'),
                'currency_id': value.get('currency'),
                field_name: self.id
            }]).id
        return cost_id

    def _delete_lines(self, model, field_name, record_id, record_ids):
        lines_of_delete = self.env[model].search([
            (field_name, '=', record_id),
            ('id', 'not in', record_ids)
        ])
        if lines_of_delete:
            lines_of_delete.unlink()

    def _compute_forecast_costs_ids(self):
        for record in self:
            project_production_ids = self.env['project.production'].search([('task_id', '=', record.id)])
            costs = {}
            cost_forecast = 0
            for production in project_production_ids:
                for unidad in production.sale_line_id.unidades_ids:
                    if unidad.product_type_calc:
                        cost_name = unidad.product_type_calc.name
                        cost_forecast += unidad.cost_subtotal * production.sale_line_id.product_uom_qty
                        if costs.get(cost_name, None):
                            costs[cost_name]['coste'] += unidad.cost_subtotal * production.sale_line_id.product_uom_qty
                            costs[cost_name]['currency'] = production.sale_line_id.currency_id.id if production.sale_line_id.currency_id else None
                            if unidad.product_type_calc.is_part_hours:
                                costs[cost_name]['qty'] += unidad.quantity
                        else:
                            costs[cost_name] = {
                                'coste': unidad.cost_subtotal * production.sale_line_id.product_uom_qty,
                                'currency': production.sale_line_id.currency_id.id if production.sale_line_id.currency_id else None,
                                'qty': unidad.quantity if unidad.product_type_calc.is_part_hours else 0
                            }

            forecast_costs_ids = []
            for key, value in costs.items():
                forecast_costs_ids.append(record._search_model_information('task.project.production.cost', 'task_id', key, value))

            record._delete_lines('task.project.production.cost', 'task_id', record.id, forecast_costs_ids)
            record.update({
                'forecast_costs_ids': forecast_costs_ids if forecast_costs_ids else None,
                'cost_forecast': cost_forecast
            })

    def _compute_real_costs_ids(self):
        for record in self:
            analytic_line_ids = self.env['account.analytic.line'].search(['|', ('task_id', '=', record.id), ('po_task_id', '=', record.id)])
            costs = {}
            cost_real = 0
            for line in analytic_line_ids:
                if line.cost_type:
                    cost_name = line.cost_type.name
                    cost_real += line.amount * -1
                    if costs.get(cost_name, None):
                        costs[cost_name]['coste'] += line.amount * -1
                        costs[cost_name]['currency'] = line.currency_id.id if line.currency_id else None
                        if line.cost_type.is_part_hours:
                            costs[cost_name]['qty'] += line.unit_amount
                    else:
                        costs[cost_name] = {
                            'coste': line.amount * -1,
                            'currency': line.currency_id.id if line.currency_id else None,
                            'qty': line.unit_amount if line.cost_type.is_part_hours else 0
                        }

            real_costs_ids = []
            for key, value in costs.items():
                real_costs_ids.append(record._search_model_information('task.account.analytic.line.cost', 'task_id', key, value))

            record._delete_lines('task.account.analytic.line.cost', 'task_id', record.id, real_costs_ids)
            record.update({
                'real_costs_ids': real_costs_ids if real_costs_ids else None,
                'cost_real': cost_real
            })

    @api.depends('cost_forecast', 'cost_real')
    def _compute_cost_deviation(self):
        for record in self:
            record.update({'cost_deviation': (record.cost_forecast - record.cost_real)})

    @api.depends('timesheet_ids')
    def _compute_coste_horas(self):
        for item in self:
            item.coste_horas = 0
            for line in item.timesheet_ids:
                item.coste_horas += abs(line.amount)


    @api.depends('material_ids')
    def _compute_coste_materiales(self):
        for item in self:
            item.coste_materiales = 0
            for line in item.material_ids:
                item.coste_materiales += line.cost_subtotal


    def _compute_coste_materiales_capitulo(self):
        for item in self:
            coste_materiales_capitulo = 0
            coste_materiales_capitulo_pct = 0
            if item.parent_id:
                capitulo_id = self.env['sale.capitulo'].search([('task_id', '=', item.parent_id.id)], limit=1)
                if capitulo_id:
                    line = capitulo_id.line_ids.filtered(lambda l: l.task_id == item)
                    if line:
                        coste_materiales_capitulo_pct = line.cost_subtotal / capitulo_id.cost_price if capitulo_id.cost_price else 0
                        coste_materiales_capitulo = item.parent_id.coste_materiales * coste_materiales_capitulo_pct

            item.update(
                {
                    'coste_materiales_capitulo': coste_materiales_capitulo,
                    'coste_materiales_capitulo_pct': coste_materiales_capitulo_pct
                }
            )


    def get_project_material_line_task(self):
        data = self.env['project.task.material'].search([('task_id', '=', self.id)])
        return data

    @api.depends('invoice_id', 'invoice_id.payment_state', 'project_id.is_billable')
    def _get_invoice_status(self):
        for rec in self:
            if not rec.project_id.is_billable:
                rec.invoice_status = 'no'
            if rec.project_id.is_billable and not rec.invoice_id:
                rec.invoice_status = 'to invoice'
            if rec.project_id.is_billable and rec.invoice_id:
                rec.invoice_status = 'invoiced'

    def _compute_show_fectura_btn(self):
        for rec in self:
            rec.show_fectura_btn = False
            if rec.project_id.is_billable and not rec.invoice_id:
                rec.show_fectura_btn = True

    def create_bill_for_material(self):
        partner_bill_dict = {}

        for rec in self:
            if rec.show_fectura_btn:
                if not rec.partner_id:
                    raise UserError(_('Seleccione un cliente para la Factura'))
                if rec.partner_id in partner_bill_dict:
                    partner_bill_dict[rec.partner_id].append(rec.id)
                else:
                    partner_bill_dict.update({rec.partner_id: [rec.id]})
        for partner_task in partner_bill_dict:
            journal_id = False
            task_ids = self.env['project.task'].browse(partner_bill_dict[partner_task])
            if task_ids:
                journal_id = task_ids[0].project_id.journal_id
            move_line_list = []
            if task_ids.mapped('material_ids'):
                for material in task_ids.mapped('material_ids'):
                    move_line_list.append((0, 0, {
                        'product_id': material.product_id.id,
                        'quantity': material.quantity,
                        'product_uom_id': material.product_id.uom_id.id,
                        'analytic_distribution': {material.task_id.project_id.analytic_account_id.id: 100},
                        'price_unit': material.price_unit,
                        'task_id': material.task_id.id,
                        'tax_ids': material.product_id.taxes_id.filtered(lambda tax: tax.company_id == self.env.company)
                    }))
            for timesheet in task_ids.mapped('timesheet_ids'):
                price_unit = 0
                employee_id = timesheet.employee_id or self.env.user.employee_id
                if timesheet.extra_hour_id:
                    product_id = timesheet.extra_hour_id
                    employee_overtime_id = employee_id.employee_overtime_ids.filtered(
                        lambda l: l.product_id == product_id)
                    if employee_overtime_id and employee_overtime_id.sale_price > 0:
                        price_unit = employee_overtime_id.sale_price
                    else:
                        price_unit = product_id.list_price
                else:
                    product_id = employee_id.product_template_id
                    if employee_id.timesheet_sale > 0:
                        price_unit = employee_id.timesheet_sale
                    elif len(task_ids.mapped('timesheet_ids')) == 0:
                        price_unit = product_id.list_price
                if not product_id:
                    raise UserError(
                        _('Defina un producto para la facturacion del parte de horas en la ficha del empleado.'))
                hour, minute = (
                1 * int(math.floor(abs(timesheet.unit_amount))), int(round((abs(timesheet.unit_amount) % 1) * 60)))
                qty = '{0:02d}.{1:02d}'.format(hour, minute)

                move_line_list.append((0, 0, {
                    'product_id': product_id.product_variant_id.id,
                    'quantity': float(qty),
                    'product_uom_id': product_id.uom_id.id,
                    'analytic_distribution': {timesheet.project_id.analytic_account_id.id: 100},
                    'price_unit': price_unit,
                    'task_id': timesheet.task_id.id,
                    'tax_ids': product_id.product_variant_id.taxes_id.filtered(
                        lambda tax: tax.company_id == self.env.company)
                }))

            invoice_vals = {
                'move_type': 'out_invoice',
                'partner_id': partner_task.id or False,
                'invoice_line_ids': move_line_list,
            }
            if partner_task.property_payment_term_id:
                invoice_vals['invoice_payment_term_id'] = partner_task.property_payment_term_id.id
            if journal_id:
                invoice_vals['journal_id'] = journal_id.id
            invoice_id = self.env['account.move'].create(invoice_vals)
            for task in task_ids:
                task.invoice_id = invoice_id

    def action_view_invoice(self):
        invoices = self.mapped('invoice_id')
        action = self.env["ir.actions.actions"]._for_xml_id("account.action_move_out_invoice_type")
        if len(invoices) > 1:
            action['domain'] = [('id', 'in', invoices.ids)]
        elif len(invoices) == 1:
            form_view = [(self.env.ref('account.view_move_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = invoices.id
        else:
            action = {'type': 'ir.actions.act_window_close'}

        context = {
            'default_move_type': 'out_invoice',
        }
        if len(self) == 1:
            context.update({
                'default_partner_id': self.partner_id.id,
                'default_invoice_origin': self.name,
            })
        action['context'] = context
        return action

    def action_open_task_invoice(self):
        return {
            'name': _('Invoice'),
            'view_mode': 'form',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'type': 'ir.actions.act_window',
            'context': self._context
        }

    @api.depends('project_id')
    def _compute_planning_count(self):
        for record in self:
            record.planning_count = self.env['planning.slot'].search_count([('parte_id', '=', record.id)])
    def action_open_planning_slot(self):
        print(self.project_id)
        return {
            'name': _('Recursos'),
            'view_mode': 'gantt',
            'res_model': 'planning.slot',
            'res_id': self.id,
            'type': 'ir.actions.act_window',
            'context': {'default_project_id': self.project_id.id,
                        'default_parte_id': self.id
                        },
            #'context': self._context
        }

    def _compute_planned_hours(self):
        for item in self:
            parte_ids = item.env['planning.slot'].search([('parte_id', '=', item.id)])
            planned_hours_task = 0
            for parte in parte_ids:
                planned_hours_task += parte.allocated_hours
            item.write({'planned_hours_task': planned_hours_task})\

    @api.depends('planned_hours_task','planned_hours')
    def _compute_hours_left(self):
        for task in self:
            hours_left = (task.planned_hours - task.planned_hours_task)
            task.write({'hours_left': hours_left})