# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class ProjectProduction(models.Model):
    _name = 'project.production'
    _description = 'Project Production'

    project_id = fields.Many2one('project.project', string="Proyecto", required=True)
    currency_id = fields.Many2one(related='project_id.analytic_account_id.currency_id', string='Moneda')
    sale_line_id = fields.Many2one('sale.order.line', string="Línea de pedido")
    product_id = fields.Many2one('product.product', string="Partida", related='sale_line_id.product_id', store=True)
    uom_id = fields.Many2one('uom.uom', string="Medida", related='sale_line_id.product_uom', store=True)
    sale_id = fields.Many2one('sale.order', string="Pedido", related='sale_line_id.order_id', store=True)
    name = fields.Char(string="Descripción", required=True)
    capitulo_id = fields.Many2one('sale.capitulo', string="Capítulo", store=True)
    price_subtotal = fields.Monetary(string="Precio Total", compute='_compute_subtotals', store=True)
    price_unit = fields.Monetary(string="Precio Ud")
    cost_unit = fields.Monetary(string="Coste Ud")
    cost_subtotal = fields.Monetary(string="Coste Total",compute='_compute_subtotals', store=True)
    quantity = fields.Float(string="Medición Proyecto")
    quantity_cost = fields.Float(string="Medición Proyecto", compute='_compute_subtotals', store=True)
    cost_unit_done = fields.Monetary(string="Coste Ud", compute='_compute_subtotals', store=True)
    quantity_done = fields.Float(string="Medición Terminada", tracking=500)
    cost_subtotal_done = fields.Monetary(string="Total Coste Medicion Terminada", compute='_compute_subtotals', store=True)
    ptje = fields.Float(string="Porcentaje terminado", tracking=500)
    task_id = fields.Many2one('project.task', string="Tarea")
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    quantity_certified = fields.Float(string="Medición Certificada", tracking=500)
    price_unit_certified = fields.Monetary(
        string="Precio Medicion Certificada",
        compute='_compute_subtotals_certified',
        store=True
    )
    price_subtotal_certified = fields.Monetary(
        string="Total Medicion Certificada",
        compute='_compute_subtotals_certified',
        store=True
    )


    @api.depends('price_unit', 'cost_unit', 'quantity','quantity_done')
    def _compute_subtotals(self):
        for production in self:
            quantity_cost = production.quantity
            cost_unit_done = production.cost_unit
            cost_subtotal = production.quantity * production.cost_unit
            price_subtotal = production.quantity * production.price_unit
            cost_subtotal_done = production.quantity_done * production.cost_unit
            capitulo_id = production.capitulo_id
            if not capitulo_id and production.sale_line_id and production.sale_line_id.capitulo_id:
                capitulo_id = production.sale_line_id.capitulo_id
            production.update(
                {
                    'cost_subtotal':cost_subtotal,
                    'price_subtotal': price_subtotal,
                    'cost_subtotal_done': cost_subtotal_done,
                    'cost_unit_done':cost_unit_done,
                    'quantity_cost':quantity_cost,
                    'capitulo_id': capitulo_id.id if capitulo_id else False
                }
            )

    @api.onchange('ptje')
    def _check_parcentage(self):
        if self.ptje > 100:
            raise ValidationError(_("Porcentaje máximo 100%"))

    def action_set_project_task(self):
        context = self._context.copy()
        context.update({'project_id': self.project_id.id if self.project_id else None})
        return {
            'name': _('Vincular tarea a la línea de producción'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'project.production.task.wizard',
            'target': 'new',
            'context': context
        }

    def action_open_project_task(self):
        return {
            'name': self.task_id.name,
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'project.task',
            'res_id': self.task_id.id
        }

    @api.onchange('price_subtotal', 'name', 'quantity')
    def _onchange_production(self):
        if self.sale_line_id:
            raise UserError(_("No se pueden cambiar cantidades o precios de líneas vinculadas a pedidos. Para ello, debe modificar el pedido"))

    @api.onchange('ptje')
    def _onchange_ptje(self):
        if self.ptje:
            self.quantity_done = (self.quantity * self.ptje) / 100

    @api.onchange('quantity_done')
    def _onchange_quantity_done(self):
        if self.quantity_done:
            self.ptje = (self.quantity_done * 100) / self.quantity

    @api.depends('price_unit')
    def _compute_subtotals_certified(self):
        for production in self:
            quantity_certified = 0
            price_unit_certified = production.price_unit
            certified_line = self.env['project.certification.line'].search([
                ('project_production_line_id', '=', production.id),
                ('certification_id.state', '=', 'invoiced')
            ], order='id DESC', limit=1)
            if certified_line:
                quantity_certified = certified_line.quantity_certified
            price_subtotal_certified = quantity_certified * production.price_unit
            production.update(
                {
                    'quantity_certified': quantity_certified,
                    'price_unit_certified': price_unit_certified,
                    'price_subtotal_certified': price_subtotal_certified,
                }
            )