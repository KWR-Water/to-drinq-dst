"""Reconcile removal tables after rebuilding the initial migration."""

from django.apps.registry import Apps
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor


def reconcile_removal_schema(
    apps: Apps,
    schema_editor: BaseDatabaseSchemaEditor,
) -> None:
    """Create only removal schema missing from an older SQLite database."""
    connection = schema_editor.connection
    citation = apps.get_model('drinq', 'Citation')
    with connection.cursor() as cursor:
        columns = {
            column.name
            for column in connection.introspection.get_table_description(
                cursor,
                citation._meta.db_table,
            )
        }
    for name in ('reference', 'doi', 'url', 'notes'):
        field = citation._meta.get_field(name)
        if field.column not in columns:
            schema_editor.add_field(citation, field)
    tables = set(connection.introspection.table_names())
    dataset = apps.get_model('drinq', 'RemovalDataset')
    for model_name in ('RemovalDataset', 'CompoundRemovalSummary'):
        model = apps.get_model('drinq', model_name)
        if model._meta.db_table not in tables:
            schema_editor.create_model(model)
    junction = dataset.sources.through
    if junction._meta.db_table not in connection.introspection.table_names():
        schema_editor.create_model(junction)


class Migration(migrations.Migration):
    dependencies = [('drinq', '0001_initial')]

    operations = [migrations.RunPython(reconcile_removal_schema)]
