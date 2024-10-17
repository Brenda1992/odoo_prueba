# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ResCompanyInherit(models.Model):
    _inherit = 'res.company'

    ptje_gastos_indirectos = fields.Float(string='% gastos indirectos')
    operation_type_id = fields.Many2one(
        'stock.picking.type',
        string='Envío Almacén - Obra',
        help='Operación para enviar desde el Almacén de la Compañía hacia la Obra'
    )
    task_creation = fields.Selection([
        ('all', 'Crea Tareas por partidas'),
        ('none', 'No crea Tareas por partidas'),
        ('task_chapter', 'Crea Tareas por capítulos')
    ],
        string="Creacion de tareas",
        default="none"
    )
    product_certificaciones_previas_id = fields.Many2one('product.template', 'Producto Certificaciones Previas')
    operation_type_entrada_id = fields.Many2one(
        'stock.picking.type',
        string='Envío Obra - Almacén',
        help='Operación para enviar desde la Obra hacia el Almacén de la Compañía'
    )
    sales_based_purchases = fields.Boolean(
        string="Compras basadas en ventas",
        help='Las unidades de obra de tipo Material generarán traspasos de forma automática, '
             'una vez confirmado el presupuesto de la obra'
    )
    operation_purchase_id = fields.Many2one(
        'stock.picking.type',
        string='Operacion Compras bajo Pedidos',
        help='Operación por defecto para las compras bajo pedidos'
    )
    task_capitulo_creation = fields.Selection(
        [
            ('all', 'Crea Tareas Padres por capitulos'),
            ('none', 'No crea Tareas Padres por capitulos')
        ],
        string="Creacion de Tareas Padres por capitulos",
        default="none"
    )
    product_retenciones_id = fields.Many2one(
        'product.template',
        string='Producto Retenciones',
    )
    billing_type = fields.Selection([
        ('origin_billing', 'Facturación Origen'),
        ('part_billing', 'Facturación Partida'),
        ('current_billing', 'Facturación Actual')
    ],
        string="Tipo Facturación",
        default="current_billing"
    )
    billing_lines = fields.Selection([
        ('all', 'Todas las líneas'),
        ('cert_lines', 'Líneas certificadas')
    ],
        string="Líneas Facturación"
    )
    previous_billings = fields.Selection([
        ('all', 'Mostrar todas'),
        ('unique_line', 'Mostrar una única línea')
    ],
        string="Facturaciones previas"
    )


    @api.onchange('billing_type')
    def onchange_billing_type(self):
        self.write({
            'billing_lines': None,
            'previous_billings': None,
        })



