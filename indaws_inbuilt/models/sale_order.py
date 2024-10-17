# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    sale_capitule_line = fields.One2many('sale.capitulo', 'order_id', copy=False)
    test_field = fields.Char("testing field")
    contact_id = fields.Many2one('res.partner', 'Contacto')

    def view_capitulos_list(self):
        action = self.env["ir.actions.actions"]._for_xml_id("indaws_inbuilt.action_capitulos_views")
        return action

    def view_sale_order_line(self):
        action = self.env["ir.actions.actions"]._for_xml_id(
            "indaws_inbuilt.action_bevia_sale_order_line")
        return action

    coste_directo = fields.Monetary(
        string='Coste Directo',
        currency_field='currency_id',
        compute='_compute_coste_directo',
        help='Coste Directo Total = Coste Mano Obra + Coste Materiales + Coste Maquinarias + Otros Costes'
    )
    margen_euros = fields.Monetary(string='Margen directo (€)', compute='_compute_margen_euros')
    margen_percentage = fields.Float(string='Margen directo (%)', compute='_compute_margen_percentage')
    ptje_gastos_indirectos = fields.Float(string='% Costes indirectos', readonly=True, store=True)
    gastos_indirectos_euros = fields.Monetary(string='Costes indirectos (€)', digits=(4, 2), compute='_compute_gastos_inderectos')
    margen_real_euros = fields.Monetary(digits=(4, 2), string='Margen real (€)', compute='_compute_margen_real_euros')
    margen_real_percentage = fields.Float(digits=(4, 2), string='Margen real (%)', compute='_compute_margen_real_percentage')
    coste_total = fields.Monetary(
        string='Coste total',
        currency_field='currency_id',
        compute='_compute_coste_total',
        help= 'Coste Total = Coste Directo + Gastos Indirectos'
    )
    direct_costs_ids = fields.One2many(
        'sale.line.unidad.cost',
        'sale_order_id',
        string='Costos directos',
        compute='_compute_direct_costs'
    )
    invoice_order = fields.Boolean('Facturar pedido?', related="type_id.invoice_order")



    def _search_sale_line_unidad_cost(self, name, value):
        line = self.env["sale.line.unidad.cost"].search([('sale_order_id', '=', self.id), ('name', '=', name)], limit=1)
        if line:
            line.coste = value.get('coste')
            line.quantity = value.get('qty')
            cost_id = line.id
        else:
            cost_id = self.env["sale.line.unidad.cost"].create([{
                'name': name,
                'coste': value.get('coste'),
                'quantity': value.get('qty'),
                'currency_id': self.currency_id.id,
                'sale_order_id': self.id
            }]).id
        return cost_id

    def get_data_direct_cost_line(self, line, costs, unidad):
        if line and unidad and unidad.product_type_calc:
            cost_name = unidad.product_type_calc.name
            if costs.get(cost_name, None):
                costs[cost_name]['coste'] += unidad.cost_subtotal * line.product_uom_qty
                if unidad.product_type_calc.is_part_hours:
                    costs[cost_name]['qty'] += unidad.quantity
            else:
                costs[cost_name] = {
                    'coste': unidad.cost_subtotal * line.product_uom_qty,
                    'qty': unidad.quantity if unidad.product_type_calc.is_part_hours else 0
                }
        elif line and line.product_id.product_type_unit:
            cost_name = line.product_id.product_type_unit.name
            if costs.get(cost_name, None):
                costs[cost_name]['coste'] += line.cost_subtotal
                if line.product_id.product_type_unit.is_part_hours:
                    costs[cost_name]['qty'] += line.product_uom_qty
            else:
                costs[cost_name] = {
                    'coste': line.cost_subtotal,
                    'qty': line.product_uom_qty if line.product_id.product_type_unit.is_part_hours else 0
                }
        return costs


    @api.depends(
        'order_line',
        'order_line.product_uom_qty',
        'order_line.unidades_ids',
        'order_line.unidades_ids.cost_subtotal'
    )
    def _compute_direct_costs(self):
        for record in self:
            costs = {}
            for line in record.order_line:
                if line.unidades_ids:
                    for unidad in line.unidades_ids:
                        costs = self.get_data_direct_cost_line(line=line, costs=costs, unidad=unidad)
                else:
                    costs = self.get_data_direct_cost_line(line=line, costs=costs, unidad=None)

            direct_costs_ids = []
            for key, value in costs.items():
                direct_costs_ids.append(record._search_sale_line_unidad_cost(key, value))

            lines_of_delete = self.env["sale.line.unidad.cost"].search([
                ('sale_order_id', '=', record.id),
                ('id', 'not in', direct_costs_ids)
            ])
            if lines_of_delete:
                lines_of_delete.unlink()

            record.direct_costs_ids = direct_costs_ids if direct_costs_ids else None


    @api.onchange('company_id')
    def _onchange_company(self):
        for rec in self.filtered(lambda l: l.company_id):
            rec.ptje_gastos_indirectos = rec.company_id.ptje_gastos_indirectos

    def _compute_gastos_inderectos(self):
        for rec in self:
            rec.gastos_indirectos_euros = rec.amount_untaxed * (rec.ptje_gastos_indirectos / 100)

    def _compute_margen_real_percentage(self):
        for record in self:
            if record.amount_untaxed != 0:
                record.margen_real_percentage = (record.margen_real_euros * 100) / record.amount_untaxed
            else:
                record.margen_real_percentage = 100

    @api.depends('amount_untaxed', 'coste_total')
    def _compute_margen_real_euros(self):
        for record in self:
            record.margen_real_euros = record.amount_untaxed - record.coste_total

    @api.model_create_multi
    def create(self, values):
        so = super().create(values)
        so.order_line.write({'order_id_domain':[(6,0,so.ids)]})
        so.write({'ptje_gastos_indirectos': so.company_id.ptje_gastos_indirectos})
        return so

    @api.depends('direct_costs_ids')
    def _compute_coste_directo(self):
        for record in self:
            record.coste_directo = sum(record.direct_costs_ids.mapped('coste'))

    @api.depends('coste_directo', 'gastos_indirectos_euros')
    def _compute_coste_total(self):
        for record in self:
            record.coste_total = record.coste_directo + record.gastos_indirectos_euros

    @api.depends('amount_untaxed', 'coste_directo')
    def _compute_margen_euros(self):
        for record in self:
            record.margen_euros = record.amount_untaxed - record.coste_directo

    @api.depends('margen_euros', 'amount_untaxed')
    def _compute_margen_percentage(self):
        for record in self:
            if record.amount_untaxed != 0:
                record.margen_percentage = (record.margen_euros * 100) / record.amount_untaxed
            else:
                record.margen_percentage = 100

    def view_sale_unidad_obra(self):
        action = self.env["ir.actions.actions"]._for_xml_id("indaws_inbuilt.action_sale_unidad_obra")
        return action

    def _create_task_for_chapter(self, capitulo):
        project_task = capitulo.task_id
        if not project_task:
            project_task = self.project_id.task_ids.create({
                'project_id': self.project_id.id,
                'name': capitulo.name,
            })
            capitulo.task_id = project_task.id
        return project_task

    def calculate_planned_hours(self, capitulo):
        planned_hours = 0
        for line in capitulo.line_ids.filtered(lambda l: l.unidades_ids):
            for unidad in line.unidades_ids.filtered(lambda u: u.product_type_calc.is_part_hours):
                planned_hours += unidad.quantity * line.product_uom_qty
        return planned_hours

    def actulizar_obra(self):
        if self.company_id.task_creation == 'all':
            for line in self.order_line:
                planned_hours = 0
                unidades_ids = line.unidades_ids.filtered(lambda u: u.product_type_calc.is_part_hours)
                for unidades in unidades_ids:
                    planned_hours += unidades.quantity * line.product_uom_qty
                # associate planned hours with the task
                if not line.task_id:
                    project_task = self.project_id.task_ids.create({
                        'project_id': self.project_id.id,
                        'name': line.name,
                        'planned_hours': planned_hours
                    })
                    line.task_id = project_task.id
                else:
                    line.task_id.write({'planned_hours': planned_hours})
        elif self.company_id.task_creation == 'task_chapter':
            for capitulo in self.sale_capitule_line:
                project_task = self._create_task_for_chapter(capitulo)
                capitulo.line_ids.write({'task_id': project_task.id})
                # Calcular horas planeadas
                project_task.write({'planned_hours': self.calculate_planned_hours(capitulo)})

        if self.project_id:
            self.project_id.add_lines()

        if self.company_id.task_capitulo_creation == 'all' and self.project_id:
            for capitulo in self.sale_capitule_line:
                project_task = self._create_task_for_chapter(capitulo)
                if project_task.name != capitulo.name:
                    project_task.write({'name': capitulo.name})
                capitulo.line_ids.mapped('task_id').write({'parent_id': project_task.id})

    def create_obra(self):
        if not self.project_id:
            return self.env["ir.actions.actions"]._for_xml_id("indaws_inbuilt.action_wizard_create_sale_obra")
        else:
            if self.company_id.task_creation == 'all':
                for line in self.order_line:
                    planned_hours = 0
                    unidades_ids = line.unidades_ids.filtered(lambda u: u.product_type_calc.is_part_hours)
                    for unidades in unidades_ids:
                        planned_hours += unidades.quantity * line.product_uom_qty
                    # Create task
                    project_task = self.project_id.task_ids.create({
                        'project_id': self.project_id.id,
                        'name': line.name,
                        'planned_hours': planned_hours
                    })
                    line.write({'task_id': project_task.id})
            elif self.company_id.task_creation == 'task_chapter':
                for capitulo in self.sale_capitule_line:
                    project_task = self._create_task_for_chapter(capitulo)
                    capitulo.line_ids.write({'task_id': project_task.id})
                    # Calcular horas planeadas
                    project_task.write({'planned_hours': self.calculate_planned_hours(capitulo)})
            self.actulizar_obra()

        if self.company_id.task_capitulo_creation == 'all' and self.project_id:
            for capitulo in self.sale_capitule_line:
                project_task = self._create_task_for_chapter(capitulo)
                capitulo.line_ids.mapped('task_id').write({'parent_id': project_task.id})

    def get_project_form(self):
        self.ensure_one()
        action = {
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', self.project_id.id)],
            'res_id': self.project_id.id,
            'view_mode': 'form',
            'name': _('Projects'),
            'res_model': 'project.project',
        }
        return action

    def action_confirm(self):
        if self.type_id and self.type_id.create_albaran:
            res = super(SaleOrder, self).action_confirm()
        else:
            for rec in self:
                if rec.company_id.sales_based_purchases and self.project_id:
                    rec.create_task_material()
            res = super(SaleOrder, self).action_confirm()
            if self.picking_ids:
                self.picking_ids.unlink()
            if self.project_id:
                self.project_id.add_lines()
        return res

    def get_unidades_id_to_purchase(self):
        unidades_ids = self.order_line.mapped('unidades_ids').filtered(lambda ud: ud.product_id.product_type_unit.is_materials == True)
        return unidades_ids

    def create_task_material(self):
        # for ud in self.get_unidades_id_to_purchase().filtered(lambda line: line.product_id.product_type_calc == 'materials'):
        for ud in self.get_unidades_id_to_purchase():
            line_id = self.env['project.task.material'].search(
                [('sale_unidad_obra_id', '=', ud.id), ('sale_id', '=', self.id)])
            # if ud.product_id.product_type_calc == 'materials' and not line_id:
            if ud.product_id.product_type_unit.is_materials and not line_id:
                qty = ud.order_line_id.product_uom_qty * ud.quantity
                self.env['project.task.material'].create({
                    'project_id': self.project_id.id,
                    'product_id': ud.product_id.id,
                    'task_id': ud.order_line_id.task_id and ud.order_line_id.task_id.id or False,
                    'quantity': qty,
                    'cost': ud.cost_unit,
                    'price_unit': ud.price_unit,
                    'sale_unidad_obra_id': ud.id,
                    'sale_id': self.id
                })

    def copy(self, default=None):
        default = default or {}
        default['project_id'] = False
        res = super(SaleOrder, self).copy(default)
        res.order_line.write({'analytic_distribution': {}})
        return res

    def _update_code_lines(self, deleted_lines=[]):
        dict_code = {}
        for line in self.order_line:
            if line.id not in deleted_lines and line.capitulo_id:
                dict_code[line.capitulo_id.id] = 1 if not dict_code.get(line.capitulo_id.id, False) else dict_code.get(line.capitulo_id.id)+1
                code = dict_code.get(line.capitulo_id.id)
                # line.write({'code': line.capitulo_id.code + '.' + (str(code).zfill(2) if (code < 10) else str(code))})
                line.write({'code': '{}.{}'.format(line.capitulo_id.code, (str(code).zfill(2) if (code < 10) else str(code)))})

    def write(self, values):
        result = super(SaleOrder, self).write(values)
        if 'analytic_account_id' in values:
            for sale in self:
                if values.get('analytic_account_id',False):
                    sale.order_line.write({'analytic_distribution': {sale.analytic_account_id.id: 100}})
                else:
                    sale.order_line.write({'analytic_distribution': {}})
        if 'order_line' in values:
            self._update_code_lines()
        return result

    def _get_update_prices_lines(self):
        """ Hook to exclude specific lines which should not be updated based on price list recomputation """
        return self.order_line.filtered(lambda line: not line.display_type and line.price_type != 'automático')

    def _update_code_capitulos(self):
        cont = 1
        for line in self.sale_capitule_line:
            line.write({'code': str(cont).zfill(2) if (cont < 10) else str(cont)})
            cont += 1