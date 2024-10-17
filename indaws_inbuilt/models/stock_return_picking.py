# -*- coding: utf-8 -*-

from odoo import fields, models, api


class ReturnPicking(models.TransientModel):
    _inherit = 'stock.return.picking'

    def _create_returns(self):
        res = super(ReturnPicking, self)._create_returns()
        for return_line in self.product_return_moves:
            if return_line.move_id.new_analytic_account_line_id:
                if return_line.move_id.product_uom_qty == return_line.quantity:
                    return_line.move_id.new_analytic_account_line_id.sudo().unlink()
                else:
                    return_line.move_id.new_analytic_account_line_id.unit_amount -= -return_line.quantity
        return res