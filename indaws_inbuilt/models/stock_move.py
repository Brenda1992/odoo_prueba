# -*- coding: utf-8 -*-

from odoo import fields, models, api


class StockMove(models.Model):
    _inherit = 'stock.move'

    analytic_account_id = fields.Many2one("account.analytic.account", string="Cuenta Analítca")#not used
    new_analytic_account_line_id = fields.Many2one("account.analytic.line")
    task_id = fields.Many2one('project.task', string="Tarea")  #not used
    material_id = fields.Many2one('project.task.material', string='Traspaso')


    def _prepare_analytic_line(self, move, amount, unit_amount, name, partner_id):
        return {
            'name': name,
            'amount': amount,
            'account_id': move.picking_id.project_id.analytic_account_id.id,
            'unit_amount': unit_amount,
            'product_id': move.product_id.id,
            'product_uom_id': move.product_id.uom_id.id,
            'company_id': move.company_id.id,
            'ref': move.picking_id.name,
            'category': 'other',
            'task_id': False,  # IF task!= False it will take it as timesheet
            'project_id': False,
            'employee_id': False,
            'po_task_id': move.task_id.id if move.task_id else False,
            'partner_id': partner_id
        }

    def _action_done(self, cancel_backorder=False):
        moves = super(StockMove, self)._action_done(cancel_backorder)
        for move in moves:
            if move.picking_id.project_id and not move.purchase_line_id: # no crea linea analitica si es una compra
                if move.material_id:
                    amount = move.product_uom_qty * move.material_id.cost
                else:
                    amount = move.product_uom_qty * move.product_id.standard_price
                unit_amount = sum(move.stock_valuation_layer_ids.mapped('quantity'))

                if (
                        (move.location_usage == 'internal' and move.location_dest_usage == 'customer') or
                        (move.location_usage == 'customer' and move.location_dest_usage == 'internal') or
                        (move.location_usage == 'supplier' and move.location_dest_usage == 'internal')
                ):
                    name = move.name
                    partner_id = False
                    new_amount = amount * -1 if move.location_usage == 'internal' else amount

                    if move.location_usage == 'supplier' and move.location_dest_usage == 'internal':
                        name = move.picking_id.name + ' ' + move.product_id.name
                        partner_id = move.picking_id.project_id.partner_id.id
                        new_amount = move.material_id.cost if move.material_id else move.product_id.standard_price

                    analytic_line_vals = self._prepare_analytic_line(move, new_amount, unit_amount, name, partner_id)
                    analytic_lines = self.env['account.analytic.line'].with_context(picking_done=True).sudo().create(analytic_line_vals)
                    move.new_analytic_account_line_id = analytic_lines.id
                    if move.material_id:
                        move.material_id.write({
                            'analytic_move_id': analytic_lines.id,
                            'quantity': move.product_uom_qty
                        })
        return moves


    # TODO las devoluciones
    # se comento por los cambios solicitados en la tarea con id 9239
    # @api.model_create_multi
    # def create(self, values):
    #     moves = super(StockMove, self).create(values)
    #     for move in moves:
        #     if move.picking_id.project_id and move.material_id and move.product_uom_qty > 0:
        #         # this is because backorder move copy task from previous move, this is needed to take the cost from original material
        #         if move.material_id.picking_id:
        #             material = self.env['project.task.material'].create({
        #                 'project_id': move.picking_id.project_id.id,
        #                 'product_id': move.product_id.id,
        #                 'quantity': move.product_uom_qty if move.location_usage == 'internal' else -move.product_uom_qty,
        #                 'picking_id': move.picking_id.id,
        #                 'cost': move.material_id.cost if move.material_id else move.product_id.standard_price,
        #                 'task_id': move.material_id.task_id.id if move.material_id and move.material_id.task_id else False,
        #                 'origin_id': move.material_id.origin_id.id if move.material_id.origin_id else False,
        #             })
        #             move.write({'material_id': material})
        #     elif move.picking_id and move.purchase_line_id and not move.material_id:
        #         if move.purchase_line_id.material_id:
        #             move.write({'material_id': move.purchase_line_id.material_id.id})
        #             move.material_id.write({'picking_id': move.picking_id.id})
        # return moves

    @api.model_create_multi
    def create(self, values):
        moves = super(StockMove, self).create(values)
        for move in moves:
            if move.picking_id and move.purchase_line_id and not move.material_id:
                if move.purchase_line_id.material_id:
                    move.write({'material_id': move.purchase_line_id.material_id.id})
            if move.material_id and move.picking_id:
                move.material_id.write({'picking_id': move.picking_id.id})
        return moves


    def write(self, values):
        if 'picking_id' in values:
            for move in self:
                if move.material_id and move.picking_id and move.picking_id.id != values['picking_id']:
                    move.material_id.write({'picking_id': values['picking_id']})
        res = super(StockMove, self).write(values)
        return res


