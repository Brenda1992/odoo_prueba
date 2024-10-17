# -*- coding: utf-8 -*-

from odoo import api, fields, models, Command, _
from odoo.exceptions import UserError, ValidationError


class WizardCreatePurchaseOrder(models.TransientModel):
    _name = 'wizard.create.purchase.order'
    _description = "Create purchase order from material"

    def default_get(self, fields_list):
        res = super(WizardCreatePurchaseOrder, self).default_get(fields_list)
        material_ids = self.env["project.task.material"].browse(
            self._context.get('active_ids') or []
        )
        if material_ids:
            res["line_ids"] = [
                Command.create({
                    'project_id': line.project_id.id,
                    'product_id': line.product_id.id,
                    'material_id': line.id,
                    'task_id': line.task_id.id,
                    'quantity': line.quantity,
                    'cost': line.cost,
                    'cost_subtotal': line.cost_subtotal})
                for line in material_ids.filtered(lambda l: not l.picking_state)
            ]
        return res

    partner_id = fields.Many2one('res.partner', string="Asignar Proveedor")
    line_ids = fields.One2many('wizard.create.purchase.order.line', 'order_id')

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        if self.partner_id:
            for line in self.line_ids:
                line.partner_id = self.partner_id

    def create_po_from_material(self):
        po_dict = {}
        shipping_address_id = False
        if self.line_ids.filtered(lambda l: not l.partner_id):
            raise UserError(_("Please select Proveedor"))
        for line in self.line_ids:
            if not shipping_address_id:
                shipping_address_id = line.project_id.shipping_address_id
            if not line.material_id.origin_id:
                if line.partner_id not in po_dict:
                    po_dict.update({line.partner_id: [line]})
                else:
                    po_dict[line.partner_id].append(line)

        picking_type_id = self.env.company.operation_purchase_id
        if not picking_type_id:
            raise ValidationError(
                _(f'No se ha definido el tipo de operacion de compras en la compañia {self.env.company.name}. \n'
                  f'Por favor configure el tipo de operacion desde los ajustes de la compañia.'))

        for partner, lines in po_dict.items():
            for line in lines:
                po_id = self.env['purchase.order'].search([
                    ('partner_id', '=', partner.id),
                    ('sale_id', '=', line.material_id.sale_id.id),
                    ('state', 'in', ['draft','sent'])
                ], limit=1)
                if not po_id:
                    dict_purchase = {
                        'partner_id': partner.id,
                        'sale_id': line.material_id.sale_id.id,
                        'picking_type_id': picking_type_id.id,
                        'dest_address_id': shipping_address_id.id if shipping_address_id else False,
                        'currency_id': self.env.company.currency_id.id,
                        'project_id': line.project_id.id if line.project_id else False,
                        'analytic_distribution': {line.project_id.analytic_account_id.id: 100} if line.project_id else False
                    }
                    po_id = self.env['purchase.order'].create(dict_purchase)
                if po_id:
                    price_unit = False
                    vals = {
                        'order_id': po_id.id,
                        'product_id': line.product_id.id,
                        'name': line.product_id.name,
                        'analytic_distribution': {line.project_id.analytic_account_id.id: 100},
                        'product_qty': line.quantity,
                        'task_id': line.task_id.id,
                        'material_id': line.material_id.id
                    }
                    seller = line.product_id._select_seller(
                        partner_id=line.partner_id,
                        quantity=line.quantity,
                        date=fields.Date.context_today(line),
                        uom_id=line.product_id.uom_po_id
                    )
                    if not seller:
                        price_unit = line.cost
                    if price_unit:
                        vals['price_unit']=price_unit

                    order_line_id = self.env['purchase.order.line'].create(vals)
                    update_material = {
                        'origin_id': po_id,
                        'origin_line_id': order_line_id.id,
                        'cost': order_line_id.price_unit,
                        'product_qty_purchase': order_line_id.product_qty,
                        'qty_received': order_line_id.qty_received,
                        'date_planned': order_line_id.date_planned
                    }
                    line.material_id.write(update_material)
                # add project in purchase
                if not po_id.project_id and line.project_id:
                    po_id.project_id = line.project_id.id



class WizardCreatePurchaseOrderLine(models.TransientModel):
    _name = 'wizard.create.purchase.order.line'
    _description = "Create purchase order line from material"

    order_id = fields.Many2one('wizard.create.purchase.order')
    task_id = fields.Many2one('project.task', string='Tarea')
    project_id = fields.Many2one('project.project', string='Project')
    quantity = fields.Float(string='Cantidad')
    cost = fields.Float(string='Coste ud')
    cost_subtotal = fields.Float(string='Precio de Coste')
    partner_id = fields.Many2one('res.partner', string="Proveedor")
    product_id = fields.Many2one('product.product', string='Producto')
    material_id = fields.Many2one('project.task.material')
