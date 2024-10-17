# -*- coding: utf-8 -*-

from odoo import api, fields, models

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    sale_id = fields.Many2one('sale.order', string='Pedido de Venta Relacionado')
    project_id = fields.Many2one('project.project', string="Obra")

    @api.onchange('project_id', 'sale_id')
    def _onchange_project(self):
        self.analytic_distribution = {self.project_id.analytic_account_id.id: 100} if self.project_id else False
        for line in self.order_line:
            line.analytic_distribution = {self.project_id.analytic_account_id.id: 100}

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('sale_id', False) and not vals.get('project_id', False):
                sale_order_id = self.env['sale.order'].browse(vals.get('sale_id'))
                vals['project_id'] = sale_order_id.project_id.id
        orders = super().create(vals_list)
        return orders

    # Se comenta debido a que ya se va a validar cada linea
    # def button_confirm(self):
    #     res = super(PurchaseOrder, self).button_confirm()
    #     for order in self.order_line:
    #         if order.task_id and order.analytic_distribution and not order.material_id:
    #             material_id = self.env['project.task.material'].create({
    #                 'product_id': order.product_id.id,
    #                 'cost': order.price_unit,
    #                 'origin_id': order.order_id.id,
    #                 'origin_line_id': order.id,
    #                 'project_id': order.task_id.project_id.id,
    #                 'task_id': order.task_id.id,
    #                 'quantity': order.product_qty,
    #                 'price_unit': order.price_unit,
    #                 'product_qty_purchase': order.product_qty,
    #                 'qty_received': order.qty_received,
    #                 'date_planned': order.date_planned
    #             })
    #             order.write({'material_id': material_id.id})
    #     return res


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    account_analytic_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account'
    )
    # task_id = fields.Many2one('project.task', string="Tarea", domain="[('project_id.analytic_account_id', '=', account_analytic_id)]")
    task_id = fields.Many2one('project.task', string="Tarea")
    material_id = fields.Many2one('project.task.material', string='Traspaso')

    @api.depends('product_id', 'date_order')
    def _compute_account_analytic_id(self):
        super(PurchaseOrderLine, self)._compute_account_analytic_id()
        for rec in self:
            if rec.order_id.project_id:
                rec.analytic_distribution = {rec.order_id.project_id.analytic_account_id.id: 100}


    def _prepare_task_material(self):
        return {
            'product_id': self.product_id.id,
            'cost': self.price_unit,
            'origin_id': self.order_id.id,
            'origin_line_id': self.id,
            'project_id': self.task_id.project_id.id,
            'task_id': self.task_id.id,
            'quantity': self.product_qty,
            'price_unit': self.price_unit,
            'product_qty_purchase': self.product_qty,
            'qty_received': self.qty_received,
            'date_planned': self.date_planned
        }


    def write(self, vals):
        res = super(PurchaseOrderLine, self).write(vals)
        for record in self:
            if record.task_id and record.analytic_distribution and not record.material_id:
                material_id = self.env['project.task.material'].create(record._prepare_task_material())
                record.write({'material_id': material_id.id})
            if 'price_unit' in vals and record.material_id:
                record.material_id.write({'cost': record.price_unit})
        return res


    @api.model_create_multi
    def create(self, vals_list):
        lines = super(PurchaseOrderLine, self).create(vals_list)
        for line in lines:
            if line.task_id and line.analytic_distribution and not line.material_id:
                material_id = self.env['project.task.material'].create(line._prepare_task_material())
                line.write({'material_id': material_id.id})
        return lines


    def _prepare_account_move_line(self, move=False):
        result = super(PurchaseOrderLine, self)._prepare_account_move_line(move)
        if self.task_id and not result.get('task_id', False):
            result.update(task_id=self.task_id.id)
        return result

    def unlink(self):
        material_id = self.material_id
        res = super(PurchaseOrderLine, self).unlink()
        if material_id:
            material_id.unlink()
        return res

    # def _prepare_account_move_line(self, move=False):
    #     res = super(PurchaseOrderLine, self)._prepare_account_move_line(move=False)
    #     if self.task_id:
    #         res.update({'task_id': self.task_id.id})
    #     return res
    #
    # def _prepare_stock_move_vals(self, picking, price_unit, product_uom_qty, product_uom):
    #     res = super(PurchaseOrderLine, self)._prepare_stock_move_vals(picking, price_unit, product_uom_qty, product_uom)
    #     if self.task_id:
    #         res.update({'task_id': self.task_id.id})
    #     if self.account_analytic_id:
    #         res.update({'analytic_account_id': self.order_id.project_id.analytic_account_id.id})
    #     return res
