# This file is part of the default_value module for Tryton.
# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from datetime import date, datetime, time
from decimal import Decimal
from time import sleep
from trytond.model import ModelView, ModelSQL, fields, Unique
from trytond.pool import Pool
from trytond.pyson import Bool, Eval
from trytond.rpc import RPC
from trytond.transaction import Transaction
import logging
import threading

__all__ = ['DefaultValue']

logger = logging.getLogger(__name__)
_FIELD_TYPES = ['boolean', 'char', 'integer', 'text', 'float', 'numeric',
    'date', 'datetime', 'time', 'many2one', 'selection', 'reference']


class DefaultValue(ModelSQL, ModelView):
    'Default Value'
    __name__ = 'default.value'
    model = fields.Many2One('ir.model', 'Model', required=True,
        states={
            'readonly': Bool(Eval('default_value')),
            })
    field = fields.Many2One('ir.model.field', 'Field', required=True,
        domain=[
            ('model', '=', Eval('model', 0)),
            ('ttype', 'in', _FIELD_TYPES),
            ], depends=['model'],
        states={
            'readonly': Bool(Eval('default_value')),
            })
    field_type = fields.Function(fields.Char('Field Type', readonly=True,
            states={
                'invisible': ~Bool(Eval('field')),
                }),
        'on_change_with_field_type')
    default_value = fields.Char('Default Value', readonly=True)
    boolean = fields.Function(fields.Boolean('Value',
            states={
                'invisible': Eval('field_type') != 'boolean',
                }),
        'get_value', setter='set_value')
    char = fields.Function(fields.Char('Value',
            states={
                'invisible': Eval('field_type') != 'char',
                }),
        'get_value', setter='set_value')
    integer = fields.Function(fields.Integer("Value",
            states={
                'invisible': Eval('field_type') != 'integer',
                }),
        'get_value', setter='set_value')
    text = fields.Function(fields.Text('Value',
            states={
                'invisible': Eval('field_type') != 'text',
                }),
        'get_value', setter='set_value')
    float = fields.Function(fields.Float('Value',
            states={
                'invisible': Eval('field_type') != 'float',
                }),
        'get_value', setter='set_value')
    numeric = fields.Function(fields.Numeric('Value',
            states={
                'invisible': Eval('field_type') != 'numeric',
                }),
        'get_value', setter='set_value')
    date = fields.Function(fields.Date('Value',
            states={
                'invisible': Eval('field_type') != 'date',
                }),
        'get_value', setter='set_value')
    datetime = fields.Function(fields.DateTime('Value',
            states={
                'invisible': Eval('field_type') != 'datetime',
                }),
        'get_value', setter='set_value')
    time = fields.Function(fields.Time('Value',
            states={
                'invisible': Eval('field_type') != 'time',
                }),
       'get_value', setter='set_value')
    many2one = fields.Function(fields.Selection('get_selection_values',
            'Value', states={
                'invisible': Eval('field_type') != 'many2one',
                }),
        'get_value', setter='set_value')
    selection = fields.Function(fields.Selection('get_selection_values',
            'Value', states={
                'invisible': Eval('field_type') != 'selection',
                }),
        'get_value', setter='set_value')
    reference = fields.Function(fields.Char('Value',
            states={
                'invisible': Eval('field_type') != 'reference',
                }),
        'get_value', setter='set_value')

    @classmethod
    def __setup__(cls):
        super(DefaultValue, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('default_uniq', Unique(t, t.field),
                'You can not define more than one default '
                    'value for the same model and field.'),
        ]
        cls._error_messages.update({
                'field_has_default_value': 'The field %s has already a default'
                    ' value.',
                'field_is_functional': 'The field %s is a functional field.',
                })
        cls.__rpc__.update({
                'get_selection_values': RPC(instantiate=0),
                })

    def get_rec_name(self, name):
        if self.model:
            return self.model.rec_name

    @fields.depends('field')
    def get_selection_values(self, name=None):
        pool = Pool()
        field = self.field
        model = field and field.model or False
        selection = [(None, '')]
        if model and field:
            if self.on_change_with_field_type() == 'selection':
                Model = pool.get(model.model)
                selection.extend(Model()._fields[field.name].selection)
            elif self.on_change_with_field_type() == 'many2one':
                Model = pool.get(field.relation)
                selection.extend((str(m.id), m.rec_name)
                    for m in Model.search([]))
        return selection

    @classmethod
    def __post_setup__(cls):
        super(DefaultValue, cls).__post_setup__()
        pool = Pool()
        Module = pool.get('ir.module')
        modules = Module.search([
            ('name', '=', 'default_value'),
            ('state', '=', 'installed'),
            ])
        if modules:
            db_name = Transaction().database.name
            thread1 = threading.Thread(target=cls.load_default_values,
                args=(db_name, Transaction().user))
            thread1.start()

    @classmethod
    def load_default_values(cls, db_name, user):
        sleep(5)
        with Transaction().start(db_name, user):
            try:
                cls.set_default_values()
            except:
                logger.warning(
                    'Error loading default values. Try reload them again by '
                    'restarting the server')

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Field = pool.get('ir.model.field')
        for val in vlist:
            field, = Field.search([('id', '=', val['field'])])
            model = pool.get(field.model.model)
            if hasattr(model, 'default_%s' % field.name):
                cls.raise_user_error('field_has_default_value',
                    error_args=field.name)
            if isinstance(model._fields[field.name], fields.Function):
                cls.raise_user_error('field_is_functional',
                    error_args=field.name)
        return super(DefaultValue, cls).create(vlist)

    @classmethod
    def write(cls, *args):
        super(DefaultValue, cls).write(*args)
        actions = iter(args)
        for default_values, _ in zip(actions, actions):
            cls.set_default_values(default_values)

    @classmethod
    def delete(cls, default_values):
        pool = Pool()
        for default_value in default_values:
            Model = pool.get(str(default_value.model.model))
            if default_value.field.name in Model._defaults:
                del Model._defaults[default_value.field.name]
        return super(DefaultValue, cls).delete(default_values)

    @classmethod
    def set_default_values(cls, default_values=None):
        pool = Pool()
        if not default_values:
            DefValue = pool.get(cls.__name__)
            default_values = DefValue.search([])
        for default_value in default_values:
            Model = pool.get(str(default_value.model.model))
            field_name = default_value.field.name
            field_type = default_value.field_type
            value = default_value.default_value
            if field_type in ('char', 'text', 'selection', 'reference'):
                def_default_function = (
                    'def default_%s():\n'
                    '    return \'%s\''
                    % (field_name, value))
            elif field_type in ('boolean', 'integer', 'float', 'many2one'):
                def_default_function = (
                    'def default_%s():\n'
                    '    return %s' %
                    (field_name, value))
            elif field_type == 'numeric':
                def_default_function = (
                    'def default_%s():\n'
                    '    return Decimal(\'%s\')' %
                    (field_name, value))
            elif field_type == 'date':
                if value:
                    def_default_function = (
                        'def default_%s():\n'
                        '    return date(%s, %s, %s)' %
                        (field_name, value[:4], value[5:7], value[8:]))
            elif field_type == 'datetime':
                if value:
                    def_default_function = (
                        'def default_%s():\n'
                        '    return datetime.strptime(\'%s\', \'%s\')' %
                        (field_name, value, '%Y-%m-%d %H:%M:%S'))
            elif field_type == 'time':
                if value:
                    def_default_function = (
                        'def default_%s():\n'
                        '    return time(%s, %s, %s)' %
                        (field_name, value[:2], value[3:5], value[6:]))
            exec def_default_function
            Model._defaults[field_name] = eval('default_%s' % field_name)

    @fields.depends('field')
    def on_change_with_field_type(self, name=None):
        return self.field.ttype if self.field else None

    @fields.depends('field_type', 'default_value')
    def get_value(self, name):
        if self.field_type == name:
            value = self.default_value
            if name == 'boolean':
                return True if value == 'True' else False
            elif name == 'integer':
                return int(value) if value else 0
            elif name == 'float':
                return float(value) if value else 0.0
            elif name == 'numeric':
                return Decimal(value) if value else Decimal('0.0')
            elif name == 'date':
                return (value
                    and date(int(value[:4]), int(value[5:7]), int(value[8:]))
                    or None)
            elif name == 'datetime':
                return (value and datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
                    or None)
            elif name == 'time':
                return (value
                    and time(int(value[:2]), int(value[3:5]), int(value[6:]))
                    or None)
            return value

    @classmethod
    def set_value(cls, default_values, name, value):
        for default_value in default_values:
            if name == default_value.field_type and value != None:
                default_value.default_value = str(value)
                default_value.save()
