import pandas as pd
from django.db.utils import IntegrityError
# from django.contrib.auth.models import User

import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dst_site.settings")

from drinq.models import Compound, CompoundCas, CompoundSynonym
from research import DPATH_RESEARCH

# Read CSV file into a DataFrame
dpath_data = os.path.join(DPATH_RESEARCH, 'data/processed')
fpath_compound = os.path.join(dpath_data, 'table_compound.csv')
fpath_cas = os.path.join(dpath_data, 'table_cas_cid.csv')
fpath_syn = os.path.join(dpath_data, 'table_synonyms_cid.csv')

dfs = {
    'compounds': pd.DataFrame(),
    'cas': pd.DataFrame(),
    'synonyms': pd.DataFrame()}

for key_, fpath in zip(dfs.keys(), [fpath_compound, fpath_cas, fpath_syn]):
    dfs[key_] = pd.read_csv(fpath_compound, sep=';')
    unnamed_columns = [col for col in dfs[key_].columns
                       if 'unnamed' in col.lower()]
    dfs[key_].drop(unnamed_columns, axis=1, inplace=True)

# Save all the new compounds
df_compound, df_cas = dfs['compounds'], dfs['cas']
compounds = [
    Compound(cid=row['cid'], common_name=row['common_name'],
             isomeric_smiles=row['IsomericSMILES'],
             )
    for _, row in df_compound.iterrows()
]

try:
    compounds_created = Compound.objects.bulk_create(compounds)
except IntegrityError:
    pass


# Iterate through the DataFrame and create model instances

for index, row in dfs['compounds'].iterrows():
    # Create or get the Compound instance
    cas_props = None
    cid, common_name, isomeric_smiles = (
        row['cid'], row['common_name'], row['IsomericSMILES'],
    )
    try:
        cas_props = df_cas[df_cas['cid'] == cid]
    except:
        pass

    compound, created = Compound.objects.get_or_create(
        cid=cid, common_name=common_name, isomeric_smiles=isomeric_smiles,
        defaults={'slug': cid.lower().replace(' ', '-')}
    )
    if cas_props is not None:
        compoundcas_kwargs = {'cid': cid, 'cas': cas_props['cas']}
    else:
        compoundcas_kwargs = {'cid': cid}

    cas, created = CompoundCas.objects.get_or_create(
        **compoundcas_kwargs, defaults={'slug': cid.lower().replace(' ', '-')}
    )

    # # Create the Product instance
    # compound = Compound(
    #     cid=cid,
    #     common_name=row['common_name'],
    #     isomeric_smiles=row['isomeric_smiles'],
    #     slug=autoslug.AutoSlugField(populate_from='cid'),
    # )

    # to save the current compound
    compound.save()

print(f"CSV data for compound {cid} has been loaded into the Django database.")
