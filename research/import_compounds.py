import pandas as pd

from typing import List, Dict
from pathlib import Path
import django
import numpy as np
from django.db.utils import IntegrityError
# from django.contrib.auth.models import User

import os
# NB: run this script from the project root directory!!
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "drinq.settings")
django.setup()
import project_path
from drinq.models import Compound, CompoundCas, CompoundSynonym

# workaround to find the research directory path instead of importing it from 
# the research module
DPATH_RESEARCH = Path(__file__).parent

dpath_data = os.path.join(DPATH_RESEARCH, 'data/processed')
FPATH_COMPOUND = os.path.join(dpath_data, 'table_compound.csv')
FPATH_CAS = os.path.join(dpath_data, 'table_cas_cid.csv')
FPATH_SYN = os.path.join(dpath_data, 'table_synonyms_cid.csv')


def run(fpath_compound: str, fpath_cas: str, fpath_syn: str):
    dfs = {
        'compounds': pd.DataFrame(),
        'cas': pd.DataFrame(),
        'synonyms': pd.DataFrame()}

    # Read CSV file into a DataFrame
    for key_, fpath in zip(dfs.keys(), [fpath_compound, fpath_cas, fpath_syn]):
        dfs[key_] = pd.read_csv(fpath, sep=';')
        unnamed_columns = [
            col for col in dfs[key_].columns if 'unnamed' in col.lower()
            ]
        dfs[key_].drop(unnamed_columns, axis=1, inplace=True)

    # Save all the new compounds
    df_compound, df_cas, df_syn = dfs['compounds'], dfs['cas'], dfs['synonyms']

    compounds = [
        Compound(
            cid=row['cid'], common_name=row['common_name'],
            isomeric_smiles=row['IsomericSMILES'],
                )
        for _, row in df_compound.iterrows()
    ]

    cas_rns, synonyms = [], []
    # Create table of CAS registry numbers
    for _, row in df_cas.iterrows():
        matched_compound = [compound for compound in compounds
                            if compound.cid == row['cid']]
        cas, cas_str = row['cas'], str(row['cas'])
        if np.isnan(cas):
            cas, cas_str = None, ""
        if matched_compound:
            cas_rns.append(
                CompoundCas(
                    cid=matched_compound[0], cas=cas,
                    slug=f'{row["cid"]}__{cas_str}',
                    )
            )
    # Create table of synonyms
    for _, row in df_syn.iterrows():
        matched_compound = [compound for compound in compounds
                            if compound.cid == row['cid']]
        if matched_compound:
            synonyms.append(
                CompoundSynonym(
                    cid=matched_compound[0], synonym=row['synonym']
                    )
            )

    # Bulk create the table entries
    table_instances = [compounds, cas_rns, synonyms]
    table_objects = [Compound, CompoundCas, CompoundSynonym]

    for table, instances in zip(table_objects, table_instances):
        try:
            created = table.objects.bulk_create(instances)
        except IntegrityError as integrity_exception:
            print('Something wrong in the db?')
            raise integrity_exception
        if created is not None:
            print(
                f'{len(created)} entries in Table {table._meta.db_table} added.'
                )


if __name__ == '__main__':
    run(
        fpath_compound=FPATH_COMPOUND, fpath_cas=FPATH_CAS, fpath_syn=FPATH_SYN
        )

