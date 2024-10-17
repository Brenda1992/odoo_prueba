# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from collections import defaultdict
import json
import io
from odoo.tools import date_utils
try:
    from odoo.tools.misc import xlsxwriter
except ImportError:
    import xlsxwriter


class Project(models.Model):
    _inherit = 'project.project'

    amount_sale = fields.Monetary(string='Importe presupuestado', compute='_get_amount_sale')
    amount_invoiced = fields.Monetary(string='Importe facturado', compute='_get_amount_invoiced')
    shipping_address_id = fields.Many2one('res.partner', string="Dirección Obra")
    project_sale_order = fields.Integer(compute='_compute_project_sale_order_count')
    project_task_material = fields.Integer(compute='_compute_project_task_material')
    currency_id = fields.Many2one(related='analytic_account_id.currency_id', string='Moneda')
    label_tasks = fields.Char(string='Nombre para Tareas', default='Tareas', translate=True)
    project_production_ids = fields.One2many('project.production', 'project_id', string="Production")
    avance_estimado = fields.Float(string="Avance Estimado", compute="_compute_avance_estimado")
    is_billable = fields.Boolean('Facturar desde Tareas', help='Permite facturar tareas de forma independiente (no para obras, para instalaciones)')
    journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Diario de Facturación",
        domain="[('type', '=', 'sale'), '|', ('company_id', '=', False), "
               "('company_id', '=', company_id)]",
        check_company=True,
    )
    purchase_orders_count = fields.Integer(
        '# Purchase Orders',
        compute='_compute_purchase_orders_count',
        groups='purchase.group_purchase_user'
    )

    def _get_project_certificate(self):
        for record in self:
            record.project_certificate = self.env['project.certification'].search_count(
                [('project_id', '=', record.id)])

    project_certificate = fields.Integer(string='Certificacions', compute='_get_project_certificate')
    show_in_report = fields.Boolean(string='Mostrar en reporte de coste', default=True)
    forecast_costs_ids = fields.One2many(
        'project.sale.order.cost',
        'project_id',
        string='Costes directos previstos',
        compute='_compute_forecast_costs_ids'
    )
    cost_forecast = fields.Float('Coste directo previsto', compute='_compute_forecast_costs_ids')
    real_costs_ids = fields.One2many(
        'project.account.analytic.line.cost',
        'project_id',
        string='Costes directos reales',
        compute='_compute_real_costs_ids'
    )
    cost_real = fields.Float('Coste directo real', compute='_compute_real_costs_ids')
    cost_deviation = fields.Float('Desviación de costes', compute='_compute_cost_deviation')
    income_deviation = fields.Float('Desviación de ingresos', compute='_compute_income_deviation')
    # Previsto
    expected_direct_margin = fields.Float('Margen directo previsto €', compute='_compute_rentabilidad_prevista')
    expected_direct_margin_percentage = fields.Float('Margen directo previsto %', compute='_compute_rentabilidad_prevista')
    indirect_costs_percentage = fields.Float('% costes indirectos', compute='_compute_rentabilidad_prevista')
    expected_indirect_costs = fields.Float('Costes indirectos previstos (€)', compute='_compute_rentabilidad_prevista')
    expected_real_margin = fields.Float('Margen real previsto €', compute='_compute_rentabilidad_prevista')
    expected_real_margin_percentage = fields.Float('Margen real previsto %', compute='_compute_rentabilidad_prevista')
    # Real
    direct_margin = fields.Float('Margen directo €', compute='_compute_rentabilidad_real')
    direct_margin_percentage = fields.Float('Margen directo %', compute='_compute_rentabilidad_real')
    indirect_costs_percentage_real = fields.Float('% costes indirectos', compute='_compute_rentabilidad_real')
    indirect_costs_real = fields.Float('Costes indirectos real (€)', compute='_compute_rentabilidad_real')
    real_margin = fields.Float('Margen real €', compute='_compute_rentabilidad_real')
    real_margin_percentage = fields.Float('Margen real %', compute='_compute_rentabilidad_real')

    @api.depends('cost_real', 'cost_forecast')
    def _compute_cost_deviation(self):
        for record in self:
            record.update({'cost_deviation': (record.cost_real - record.cost_forecast)})

    @api.depends('amount_invoiced', 'amount_sale')
    def _compute_income_deviation(self):
        for record in self:
            record.update({'income_deviation': (record.amount_invoiced - record.amount_sale)})

    @api.depends('amount_sale', 'cost_forecast', 'company_id', 'company_id.ptje_gastos_indirectos')
    def _compute_rentabilidad_prevista(self):
        for record in self:
            expected_direct_margin = record.amount_sale - record.cost_forecast
            expected_direct_margin_percentage = (expected_direct_margin / record.amount_sale) * 100 if record.amount_sale > 0 else 0
            indirect_costs_percentage = record.company_id.ptje_gastos_indirectos
            expected_indirect_costs = (indirect_costs_percentage / 100) * record.amount_sale
            expected_real_margin = expected_direct_margin - expected_indirect_costs
            expected_real_margin_percentage = (expected_direct_margin / record.amount_sale) * 100 if record.amount_sale > 0 else 0
            record.update({
                'expected_direct_margin': expected_direct_margin,
                'expected_direct_margin_percentage': expected_direct_margin_percentage,
                'indirect_costs_percentage': indirect_costs_percentage,
                'expected_indirect_costs': expected_indirect_costs,
                'expected_real_margin': expected_real_margin,
                'expected_real_margin_percentage': expected_real_margin_percentage
            })

    @api.depends('amount_invoiced', 'cost_real', 'company_id', 'company_id.ptje_gastos_indirectos')
    def _compute_rentabilidad_real(self):
        for record in self:
            direct_margin = record.amount_invoiced - record.cost_real
            direct_margin_percentage = (direct_margin / record.amount_invoiced) * 100 if record.amount_invoiced > 0 else 0
            indirect_costs_percentage_real = record.company_id.ptje_gastos_indirectos
            indirect_costs_real = (indirect_costs_percentage_real / 100) * record.amount_invoiced
            real_margin = direct_margin - indirect_costs_real
            real_margin_percentage = (direct_margin / record.amount_invoiced) * 100 if record.amount_invoiced > 0 else 0
            record.update({
                'direct_margin': direct_margin,
                'direct_margin_percentage': direct_margin_percentage,
                'indirect_costs_percentage_real': indirect_costs_percentage_real,
                'indirect_costs_real': indirect_costs_real,
                'real_margin': real_margin,
                'real_margin_percentage': real_margin_percentage
            })

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

    def get_data_forecast_costs_line(self, production, costs, unidad, cost_forecast):
        if production and unidad and unidad.product_type_calc:
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
        elif production and production.sale_line_id and production.sale_line_id.product_id.product_type_unit:
            cost_forecast += production.sale_line_id.cost_subtotal
            cost_name = production.sale_line_id.product_id.product_type_unit.name
            if costs.get(cost_name, None):
                costs[cost_name]['coste'] += production.sale_line_id.cost_subtotal
                costs[cost_name]['currency'] = production.sale_line_id.currency_id.id if production.sale_line_id.currency_id else None
                if production.sale_line_id.product_id.product_type_unit.is_part_hours:
                    costs[cost_name]['qty'] += production.sale_line_id.product_uom_qty
            else:
                costs[cost_name] = {
                    'coste': production.sale_line_id.cost_subtotal,
                    'currency': production.sale_line_id.currency_id.id if production.sale_line_id.currency_id else None,
                    'qty': production.sale_line_id.product_uom_qty if production.sale_line_id.product_id.product_type_unit.is_part_hours else 0
                }
        return costs, cost_forecast

    def _compute_forecast_costs_ids(self):
        for record in self:
            sale_order_ids = self.env['sale.order'].search([('project_id', '=', record.id)])
            project_production_ids = self.env['project.production'].search([('sale_id', 'in', sale_order_ids.ids)])
            costs = {}
            cost_forecast = 0
            for production in project_production_ids:
                if production.sale_line_id.unidades_ids:
                    for unidad in production.sale_line_id.unidades_ids:
                        costs, cost_forecast = self.get_data_forecast_costs_line(production=production, costs=costs, unidad=unidad, cost_forecast=cost_forecast)
                else:
                    costs, cost_forecast = self.get_data_forecast_costs_line(production=production, costs=costs, unidad=None, cost_forecast=cost_forecast)

            forecast_costs_ids = []
            for key, value in costs.items():
                forecast_costs_ids.append(record._search_model_information('project.sale.order.cost', 'project_id', key, value))

            record._delete_lines('project.sale.order.cost', 'project_id', record.id, forecast_costs_ids)
            record.update({
                'forecast_costs_ids': forecast_costs_ids if forecast_costs_ids else None,
                'cost_forecast': cost_forecast
            })

    def _compute_real_costs_ids(self):
        for record in self:
            analytic_line_ids = self.env['account.analytic.line'].search([('account_id', '=', record.analytic_account_id.id)])
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
                real_costs_ids.append(record._search_model_information('project.account.analytic.line.cost', 'project_id', key, value))

            record._delete_lines('project.account.analytic.line.cost', 'project_id', record.id, real_costs_ids)
            record.update({
                'real_costs_ids': real_costs_ids if real_costs_ids else None,
                'cost_real': cost_real
            })

    def get_project_material(self):
        self.ensure_one()
        ctx = self._context.copy()
        ctx['default_project_id'] = self.id
        return {
            'name': 'Traspasos',
            'view_mode': 'tree,form',
            'res_model': 'project.task.material',
            'type': 'ir.actions.act_window',
            'domain': [('project_id', '=', self.id)],
            'context': ctx,
        }

    def get_project_sale_order(self):
        action = self.env["ir.actions.actions"]._for_xml_id("sale.action_orders")
        sale_orders = self.env['sale.order'].search([('project_id', '=', self.id)])
        ctx = self._context.copy()
        ctx['default_project_id'] = self.id
        action.update(
            domain=[('id', 'in', sale_orders.ids)],
            context=ctx
        )
        return action

    def _get_amount_sale(self):
        for record in self:
            sale_orders = self.env['sale.order'].search([('project_id', '=', record.id)])
            amount = 0
            for rec in sale_orders:
                amount += rec.amount_untaxed
            record.amount_sale = amount

    def _get_amount_invoiced(self):
        for record in self:
            analytic_account_id = record.analytic_account_id
            amount = 0
            if analytic_account_id:
                analytic_line_ids = self.env['account.analytic.line'].search([('account_id','=',analytic_account_id.id),('move_line_id','!=',False)])
                invoice_lines = analytic_line_ids.mapped('move_line_id')
                invoices = invoice_lines.mapped('move_id').filtered(
                    lambda r: r.move_type in ('out_invoice', 'out_refund') and r.state not in ('draft', 'cancel'))
                amount = sum(invoices.mapped('amount_untaxed'))
            record.amount_invoiced = amount

    def _compute_project_sale_order_count(self):
        for record in self:
            sale_order_count = self.env['sale.order'].search_count([('project_id', '=', record.id)])
            record.project_sale_order = sale_order_count

    def _compute_project_task_material(self):
        for record in self:
            material_count = self.env['project.task.material'].search_count([('project_id', '=', record.id)])
            # current_opened_project = self.env['project.task.material'].search([('project_id', '=', record.id)])
            # current_opened_project.project_id = record.id
            record.project_task_material = material_count

    @api.depends('timesheet_ids')
    def _compute_total_timesheet_time(self):

        #ADD employee_id in domain because is taking materials as timesheet

        timesheets_read_group = self.env['account.analytic.line'].read_group(
            [('project_id', 'in', self.ids),('employee_id','!=',False),('indaws_analytic_line','=',False)],
            ['project_id', 'unit_amount', 'product_uom_id'],
            ['project_id', 'product_uom_id'],
            lazy=False)
        timesheet_time_dict = defaultdict(list)
        uom_ids = set(self.timesheet_encode_uom_id.ids)

        for result in timesheets_read_group:
            uom_id = result['product_uom_id'] and result['product_uom_id'][0]
            if uom_id:
                uom_ids.add(uom_id)
            timesheet_time_dict[result['project_id'][0]].append((uom_id, result['unit_amount']))

        uoms_dict = {uom.id: uom for uom in self.env['uom.uom'].browse(uom_ids)}
        for project in self:
            # Timesheets may be stored in a different unit of measure, so first
            # we convert all of them to the reference unit
            # if the timesheet has no product_uom_id then we take the one of the project
            total_time = sum([
                unit_amount * uoms_dict.get(product_uom_id, project.timesheet_encode_uom_id).factor_inv
                for product_uom_id, unit_amount in timesheet_time_dict[project.id]
            ], 0.0)
            # Now convert to the proper unit of measure set in the settings
            total_time *= project.timesheet_encode_uom_id.factor
            project.total_timesheet_time = int(round(total_time))

    def action_show_timesheets_by_employee_invoice_type(self):
        action = self.env["ir.actions.actions"]._for_xml_id("hr_timesheet.timesheet_action_all")
        #Let's put the chart view first
        new_views = []
        for view in action['views']:
            new_views.insert(0, view) if view[1] == 'tree' else new_views.append(view)
        action.update({
            'display_name': _("Timesheets"),
            'domain': [('project_id', '=', self.id),('employee_id','!=',False),('indaws_analytic_line','=',False)],
            'context': {
                'default_project_id': self.id,
                'search_default_groupby_employee': True,
                'search_default_groupby_timesheet_invoice_type': True
            },
            'views': new_views
        })

        return action

    @api.depends('project_production_ids')
    def _compute_avance_estimado(self):
        for rec in self:
            rec.avance_estimado = False
            qty = 0
            total = 0
            for line in rec.project_production_ids:
                qty = qty + 1
                total = total + line.ptje
            if qty > 0:
                rec.avance_estimado = (total / qty)

    def add_lines(self):
        sale_order_ids = self.env['sale.order'].search([('project_id', '=', self.id), ('state', 'not in', ['draft', 'cancel'])])
        production_line = [line.sale_line_id.id for line in self.project_production_ids]
        new_lines = []
        for line in sale_order_ids.mapped('order_line'):
            if not line.id in production_line:
                new_lines.append(
                    (0, 0, {
                        'sale_line_id': line.id,
                        'name': line.product_id.description_sale if line.product_id.description_sale else line.name,
                        'capitulo_id': line.capitulo_id.id,
                        'quantity': line.product_uom_qty,
                        'price_unit': line.price_unit,
                        'price_subtotal': line.price_unit,
                        'cost_unit': line.purchase_price,
                        'cost_subtotal': line.price_subtotal,
                        'task_id': line.task_id.id
                    })
                )
            else:
                self.project_production_ids.filtered(lambda pline: pline.sale_line_id.id == line.id).write(
                    {
                        'sale_line_id': line.id,
                        'name': line.product_id.description_sale if line.product_id.description_sale else line.name,
                        'capitulo_id': line.capitulo_id.id,
                        'quantity': line.product_uom_qty,
                        'price_unit': line.price_unit,
                        'price_subtotal': line.price_unit,
                        'cost_unit': line.purchase_price,
                        'cost_subtotal': line.price_subtotal,
                        'task_id': line.task_id.id
                    }
                )
        if len(new_lines):
            self.write({'project_production_ids':new_lines})

    def get_project_certification(self):
        action = self.env["ir.actions.actions"]._for_xml_id(
            "indaws_inbuilt."
            "action_project_certification"
        )
        action['domain'] = [('project_id', '=', self.id)]
        return action

    def show_cost_report(self):
        action = self.env["ir.actions.actions"]._for_xml_id(
            "indaws_inbuilt."
            "action_project_production_view_report_only_one"
        )
        action['domain'] = [('project_id', '=', self.id)]
        return action

    def action_projects_global_report(self):
        data = {
            'ids': self._context.get('active_ids'),
            'model': self._context.get('active_model'),
        }
        return {
            'type': 'ir.actions.report',
            'data': {
                'model': 'project.project',
                'options': json.dumps(data, default=date_utils.json_default),
                'output_format': 'xlsx',
                'report_name': 'Project Global Report'
            },
            'report_type': 'xlsx'
        }

    def get_xlsx_report(self, data, response):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Global Report')
        worksheet.set_column('A:A', 10)
        worksheet.set_column('B:B', 10)
        worksheet.set_column('C:C', 10)
        format0 = workbook.add_format({'bold': True})
        highlighter = workbook.add_format({'bold':True, 'bg_color': 'FFC7CE'})
        project_ids = self.env['project.project'].browse(data.get('ids'))
        row = 3
        for project in project_ids:
            worksheet.merge_range('A'+str(row)+':C'+str(row), project.name, format0)
            worksheet.write(row, 0, 'TAREA', highlighter)
            worksheet.write(row, 1, 'MATERIAL', highlighter)
            worksheet.write(row, 2, 'HORA', highlighter)
            row = row + 1
            total_material_cost = 0
            total_timesheet_cost = 0
            for task in project.task_ids:
                material_cost = sum(task.material_ids.mapped('cost'))
                timesheet_cost = sum(task.timesheet_ids.mapped('employee_id').mapped('hourly_cost'))
                total_material_cost += material_cost
                total_timesheet_cost += timesheet_cost
                worksheet.write(row, 0, task.name)
                worksheet.write(row, 1, material_cost)
                worksheet.write(row, 2, timesheet_cost)
                row = row + 1
            worksheet.write(row, 0, 'Totales', format0)
            worksheet.write(row, 1, total_material_cost, format0)
            worksheet.write(row, 2, total_timesheet_cost, format0)
            row = row + 4
        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()


    def get_project_material_line(self):
        data = self.env['project.task.material'].read_group(
            domain=[('project_id', '=', self.id)],
            fields=['product_id', 'quantity', 'cost', 'price_unit'],
            groupby=['product_id','cost'],
        )
        return data

    def get_project_material_line_task(self):
        data = self.env['project.task.material'].search([('project_id', '=', self.id)], order='task_id')
        return data

    @api.depends('analytic_account_id')
    def _compute_purchase_orders_count(self):
        for project in self:
            project.purchase_orders_count = self.env['purchase.order'].search_count([('project_id', '=', project.id)])

    def action_open_project_purchase_orders(self):
        purchase_orders = self.env['purchase.order'].search([
            ('project_id','=',self.id)
        ])
        action_window = {
            'name': _('Purchase Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'views': [[False, 'tree'], [False, 'form']],
            'domain': [('id', 'in', purchase_orders.ids)],
            'context': {
                'create': False,
            }
        }
        if len(purchase_orders) == 1:
            action_window['views'] = [[False, 'form']]
            action_window['res_id'] = purchase_orders.id
        return action_window