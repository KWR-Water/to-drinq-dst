# technology : {optimizer_name: django_name}
# Rapid sand filtration, single: 18

# the optimized parameters can be found in the <technology>_results.json files

output_pystim_to_dst = {
    18: {
        'surf_m2': 10,
        'lbed_m': 135,
    },
    # ...
}

# These are the properties that are used in the optimization, but they are not 
# necessarily optimized themselves
techprop_dst_to_pystim = {
    18: {
        <property number 'filter area'>: 'surf_m2',
        <property number 'sand_media_grain_size'>: 'diam_mm',
        <property number 'sand_porosity'>: '?',
        <property number 'sand filter bed height'>: 'lbed_m',
    },
}

inputs_wq_dst_to_pystim ={}

# There is a mapping for the input design parameters:
inputdesign_dst_to_pystim = {
    10: 'r_nom',  # (nominal) interest rate
    9: 'n_years',  # depreciation period
}
# NB The inflation rate is not used within Django.

""" 
With the information above, 3 database tables will be created (only 
once): one for the technology properties, one for the water quality 
properties, and one for the input design parameters.

@Greg: instead of doing the mapping in this Python file, 
it would be better to make 3 CSV files which can be imported in the 
database.

Table technology_wqpar_pystim, with columns:
#  id, technology_id, wqpar_id, pystim_name
Table technology_property_pystim, with columns:
#  id, technology_id, property_id, pystim_name
Table input_design_parameter_pystim, with columns:
#  id, input_design_parameter_id, pystim_name

Additionally, to be able to fetch the optimized values, the table 
technology_property will be extended with a new column 
`get_from_optimizer`. We have to think whether we want to store and 
fetch the output water quality parameters as well. In that case, the 
table technology_wqpar should be extended with a new column
`get_from_optimizer` as well.

In Django, after hitting the optimization button, the optimization will be run 
and reads django_outputs.csv, config_<>.json files and in_wq_params.json. 
After the optimization, the optimized values are stored in <technology>_results.json. 
These optimized results should be either:
  1) digested by a regex expression to extract the optimized values out from this 
  JSON and store them in the database, or
  2) the 'optimal variables' are stored in a separate CSV or (maybe better) a 
  separate json file (django_inputs.json), which can be read using the 
  `get_from_optimizer` filtered properties, reading the JSON 
  (or CSV) file and storing the values in the database.
Option 2 is the preferred one, as it is more robust and less error-prone.

Optimized values will be stored in the table treatmentplant_propertyvalue. 
"""