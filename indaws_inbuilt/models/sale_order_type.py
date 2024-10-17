
from odoo import api, fields, models


class SaleOrderTypology(models.Model):
    _inherit = "sale.order.type"


    create_albaran = fields.Boolean('Crear Albaran?')
    invoice_order = fields.Boolean('Facturar pedido?')
